# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Model Context Protocol (MCP) runtime for Elyan-class agents.

Two layers:

- ``MCPAgent`` is a framework-free tool registry and conversation context
  with Beacon and Grazer registered as default tools. It emits tool
  definitions in MCP form (``inputSchema`` plus behavior ``annotations``) or
  as OpenAI-style function tools for chat-completion APIs.
- ``MCPAgent.to_mcp_server()`` / ``serve()`` expose those tools, and the
  agent's SophiaCore persona as an MCP prompt, through the official MCP
  Python SDK (``pip install 'shaprai[mcp]'``) over stdio or streamable HTTP.
  The SDK handles protocol version negotiation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional

from shaprai.sanctuary.principles import get_ethics_prompt

logger = logging.getLogger(__name__)

EngageAction = Literal["comment", "review", "claim", "upvote", "reply"]
TEXT_ACTIONS = ("comment", "review", "reply")
# Same bar as GeneratedResponse.is_quality
ENGAGE_MIN_QUALITY = 0.8


@dataclass
class MCPTool:
    """A tool registered with an MCP agent.

    Attributes:
        name: Tool identifier.
        description: Human-readable description.
        parameters: JSON Schema for tool parameters (MCP ``inputSchema``).
        handler: Callable that executes the tool. When served over MCP, the
            SDK validates arguments against the handler's type hints, so
            annotate handlers precisely.
        title: Optional human-readable display name.
        annotations: MCP tool behavior hints: ``readOnlyHint``,
            ``destructiveHint``, ``idempotentHint``, ``openWorldHint``.
        publishes: The tool acts publicly as the agent (posts, reviews,
            claims). Such tools are left out of the MCP server, of
            ``get_tools_schema()`` and of ``execute_tool()`` unless publishing
            is allowed explicitly. This keeps them away from models and
            clients by default; it is a guard against accidents, not an
            authorization boundary for code running as the user.
    """

    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]
    title: Optional[str] = None
    annotations: Dict[str, bool] = field(default_factory=dict)
    publishes: bool = False


@dataclass
class MCPMessage:
    """A message in the MCP conversation.

    Attributes:
        role: Message role (system, user, assistant, tool).
        content: Message text content.
        tool_calls: Optional list of tool call requests.
        tool_results: Optional list of tool results.
        timestamp: Message creation time.
    """

    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None
    timestamp: float = field(default_factory=time.time)


class MCPAgent:
    """Native MCP agent with tool registration and SophiaCore principles.

    This is the lightest-weight runtime option. It manages the conversation
    context, tool registry, and system prompt injection without any
    framework dependencies.

    Attributes:
        name: Agent identifier.
        system_prompt: System prompt with SophiaCore principles.
        tools: Dictionary of registered tools.
        history: Conversation history.
    """

    def __init__(
        self,
        name: str,
        additional_prompt: str = "",
        max_history: int = 100,
    ) -> None:
        """Initialize a native MCP agent.

        Beacon and Grazer are registered as default tools.

        Args:
            name: Unique agent identifier.
            additional_prompt: Extra system prompt content.
            max_history: Maximum conversation history length.
        """
        self.name = name
        self.max_history = max_history
        self.tools: Dict[str, MCPTool] = {}
        self.history: List[MCPMessage] = []
        # One responder per agent, so its hourly rate limit applies across calls
        self._responder: Any = None

        # Build system prompt with SophiaCore principles
        ethics = get_ethics_prompt()
        self.system_prompt = ethics
        if additional_prompt:
            self.system_prompt += f"\n\n---\n\n{additional_prompt}"

        # Register default tools
        self._register_default_tools()

    @classmethod
    def from_manifest(cls, manifest: Dict[str, Any]) -> "MCPAgent":
        """Create an MCPAgent whose system prompt matches the one it was trained with.

        Args:
            manifest: Agent manifest dictionary.

        Returns:
            Configured MCPAgent instance.
        """
        from shaprai.training.recipes import build_system_prompt

        agent = cls(name=manifest.get("name", "unnamed"))
        agent.system_prompt = build_system_prompt(manifest)
        return agent

    def _register_default_tools(self) -> None:
        """Register Beacon and Grazer as default tools."""
        self.register_tool(
            MCPTool(
                name="beacon_heartbeat",
                title="Beacon heartbeat",
                description="Send a heartbeat to the Beacon discovery service to confirm agent is alive.",
                parameters={
                    "type": "object",
                    "properties": {
                        "metrics": {
                            "type": "object",
                            "description": "Optional metrics to include in heartbeat",
                        },
                    },
                },
                handler=self._beacon_heartbeat,
                annotations={
                    "readOnlyHint": False,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": True,
                },
            )
        )

        self.register_tool(
            MCPTool(
                name="grazer_discover",
                title="Discover content",
                description="Discover relevant content across platforms using Grazer.",
                parameters={
                    "type": "object",
                    "properties": {
                        "platforms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Platforms to search (github, moltbook, bottube)",
                        },
                        "topics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Topic filters",
                        },
                    },
                    "required": ["platforms"],
                },
                handler=self._grazer_discover,
                annotations={"readOnlyHint": True, "openWorldHint": True},
            )
        )

        self.register_tool(
            MCPTool(
                name="grazer_engage",
                title="Engage with content",
                description=(
                    "Engage with discovered content. comment/review/reply post "
                    "text, which must mention the post's title, author or a "
                    "topic; claim/upvote take no text."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "target_url": {
                            "type": "string",
                            "description": "URL to engage with",
                        },
                        "action": {
                            "type": "string",
                            "enum": ["comment", "review", "claim", "upvote", "reply"],
                        },
                        "content": {
                            "type": "string",
                            "description": "Text for comment/review/reply",
                        },
                        "post_title": {
                            "type": "string",
                            "description": "Title of the post being answered",
                        },
                        "post_author": {
                            "type": "string",
                            "description": "Author of the post being answered",
                        },
                        "post_topics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Topics of the post being answered",
                        },
                    },
                    "required": ["target_url", "action"],
                },
                handler=self._grazer_engage,
                annotations={
                    "readOnlyHint": False,
                    "destructiveHint": False,
                    "idempotentHint": False,
                    "openWorldHint": True,
                },
                publishes=True,
            )
        )

    def register_tool(self, tool: MCPTool) -> None:
        """Register a tool with the agent.

        Args:
            tool: MCPTool instance to register.
        """
        self.tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def get_tools_schema(
        self, format: str = "mcp", include_publishing: bool = False
    ) -> List[Dict[str, Any]]:
        """Get JSON Schema descriptions of the registered tools.

        Args:
            format: ``"mcp"`` for MCP tool definitions (``inputSchema``,
                ``title``, ``annotations``), or ``"openai"`` for
                OpenAI-compatible chat-completion ``tools`` entries.
            include_publishing: Also describe tools that act publicly as the
                agent (``grazer_engage``). Off by default so a tool list
                handed to a model can't post.

        Returns:
            List of tool schema dictionaries.
        """
        tools = [
            tool
            for tool in self.tools.values()
            if include_publishing or not tool.publishes
        ]
        if format == "openai":
            return [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]
        if format != "mcp":
            raise ValueError(
                f"Unknown tool schema format '{format}' (use 'mcp' or 'openai')"
            )

        schemas = []
        for tool in tools:
            schema: Dict[str, Any] = {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.parameters,
            }
            if tool.title:
                schema["title"] = tool.title
            if tool.annotations:
                schema["annotations"] = dict(tool.annotations)
            schemas.append(schema)
        return schemas

    def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        allow_publishing: bool = False,
    ) -> Any:
        """Execute a registered tool.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            allow_publishing: Permit tools that act publicly as the agent.

        Returns:
            Tool execution result.

        Raises:
            KeyError: If the tool is not registered.
            PermissionError: If the tool publishes and publishing wasn't allowed.
        """
        if tool_name not in self.tools:
            raise KeyError(
                f"Tool '{tool_name}' not registered. Available: {list(self.tools.keys())}"
            )

        tool = self.tools[tool_name]
        if tool.publishes and not allow_publishing:
            raise PermissionError(
                f"Tool '{tool_name}' acts publicly as the agent; pass "
                "allow_publishing=True to run it."
            )
        logger.info("Executing tool: %s", tool_name)
        result = tool.handler(**arguments)
        return result

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the conversation history.

        Args:
            role: Message role (system, user, assistant, tool).
            content: Message content.
            **kwargs: Additional message fields.
        """
        msg = MCPMessage(role=role, content=content, **kwargs)
        self.history.append(msg)

        # Trim history if needed (keep system prompt)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]

    def get_context(self) -> List[Dict[str, str]]:
        """Get the full conversation context for LLM input.

        Returns:
            List of message dictionaries with role and content.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        for msg in self.history:
            messages.append({"role": msg.role, "content": msg.content})
        return messages

    # ------------------------------------------------------------------- #
    #  MCP server
    # ------------------------------------------------------------------- #

    def to_mcp_server(self, allow_publishing: bool = False) -> Any:
        """Build an MCP server exposing this agent's tools and persona prompt.

        Args:
            allow_publishing: Also expose tools that act publicly as the agent
                (``grazer_engage``). Off by default: any connected MCP client
                could otherwise post as the agent.

        Returns:
            ``mcp.server.mcpserver.MCPServer`` instance.

        Raises:
            ImportError: If the MCP SDK (``mcp>=2``) is not installed.
        """
        try:
            from mcp.server.mcpserver import MCPServer
            from mcp_types import ToolAnnotations
        except ImportError:
            raise ImportError(
                "MCP SDK not installed. Install with: pip install 'shaprai[mcp]'"
            )

        server = MCPServer(
            name=f"shaprai-{self.name}",
            instructions=(
                f"Tools of the Elyan-class agent '{self.name}'. Fetch the "
                "'persona' prompt for the principles and voice it operates under."
            ),
        )
        for tool in self.tools.values():
            if tool.publishes and not allow_publishing:
                continue
            server.add_tool(
                tool.handler,
                name=tool.name,
                title=tool.title,
                description=tool.description,
                annotations=(
                    ToolAnnotations(**tool.annotations) if tool.annotations else None
                ),
            )

        system_prompt = self.system_prompt

        @server.prompt(
            name="persona",
            description=f"SophiaCore principles and persona of '{self.name}'.",
        )
        def persona() -> str:
            return system_prompt

        return server

    def serve(
        self, transport: str = "stdio", allow_publishing: bool = False, **kwargs: Any
    ) -> None:
        """Run this agent as an MCP server (blocks).

        Args:
            transport: ``"stdio"`` or ``"streamable-http"``.
            allow_publishing: Expose tools that act publicly as the agent.
            **kwargs: Transport options, e.g. ``host``/``port`` for HTTP.
        """
        self.to_mcp_server(allow_publishing=allow_publishing).run(transport, **kwargs)

    # ------------------------------------------------------------------- #
    #  Default tool handlers
    # ------------------------------------------------------------------- #

    def _beacon_heartbeat(
        self, metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Beacon heartbeat tool handler."""
        try:
            from shaprai.integrations.beacon import update_heartbeat

            success = update_heartbeat(self.name, metrics)
            return {"status": "ok" if success else "failed"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def _grazer_discover(
        self,
        platforms: List[str],
        topics: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Grazer discovery tool handler."""
        try:
            from shaprai.integrations.grazer.discovery import (
                DiscoveryConfig,
                GrazerDiscovery,
            )

            discovery = GrazerDiscovery(
                DiscoveryConfig(platforms=platforms, topics=topics or [])
            )
            return [asdict(post) for post in discovery.discover(self.name)]
        except Exception as e:
            return [{"status": "error", "reason": str(e)}]

    def _grazer_engage(
        self,
        target_url: str,
        action: EngageAction,
        content: Optional[str] = None,
        post_title: str = "",
        post_author: str = "",
        post_topics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Grazer engagement tool handler.

        Text engagements (comment, review, reply) must describe the post they
        answer and pass the responder's spam floor: enough distinct words, no
        stock phrases, and a mention of the post's title, author or a topic.
        That filters boilerplate; it does not judge whether the text is right.
        claim and upvote carry no text. All engagements share the agent's
        hourly rate limit.
        """
        try:
            from shaprai.integrations.grazer.discovery import DiscoveredPost
            from shaprai.integrations.grazer.responder import (
                GeneratedResponse,
                GrazerResponder,
                ResponderConfig,
            )

            if self._responder is None:
                self._responder = GrazerResponder(ResponderConfig())
            responder = self._responder

            post = DiscoveredPost(
                post_id=target_url,
                platform="",
                title=post_title.strip(),
                content="",
                author=post_author.strip(),
                url=target_url,
                topics=[t.strip() for t in post_topics or [] if t.strip()],
                relevance_score=0.0,
            )
            text = (content or "").strip()
            quality = 1.0  # upvote/claim carry no text to judge
            if action in TEXT_ACTIONS:
                if not text:
                    return {
                        "status": "rejected",
                        "reason": f"'{action}' requires content",
                    }
                if not (post.title or post.author or post.topics):
                    return {
                        "status": "rejected",
                        "reason": f"'{action}' requires post_title, post_author "
                        "or post_topics for the post being answered",
                    }
                quality = responder._score_response(text, post)
                if quality < ENGAGE_MIN_QUALITY:
                    return {
                        "status": "rejected",
                        "reason": f"content failed the quality gate ({quality:.2f} < "
                        f"{ENGAGE_MIN_QUALITY}); write a specific reply of at least "
                        f"{responder.config.min_words} words that mentions the post",
                        "quality_score": quality,
                    }
            elif text:
                return {
                    "status": "rejected",
                    "reason": f"'{action}' takes no content",
                }
            if not responder._can_respond():
                return {
                    "status": "rejected",
                    "reason": "rate limit reached "
                    f"({responder.config.max_responses_per_hour}/hour)",
                }
            responder._hour_count += 1
            response = GeneratedResponse(
                post=post, response_text=text, quality_score=quality, action=action
            )
            return responder.submit_response(response, self.name)
        except Exception as e:
            return {"status": "error", "reason": str(e)}
