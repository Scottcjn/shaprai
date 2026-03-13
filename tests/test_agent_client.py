# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elyan Labs — https://github.com/Scottcjn/shaprai
"""Unit tests for AgentClient.

Tests cover initialization, chat functionality, and edge cases.
"""

import pytest
from shaprai.core.agent_client import AgentClient


class TestAgentClientInitialization:
    """Test AgentClient initialization."""

    def test_init_with_basic_config(self):
        """Test initialization with basic agent config."""
        config = {
            "name": "test-agent",
            "model": {"base": "Qwen/Qwen3-7B-Instruct"}
        }
        client = AgentClient("test-agent", config)
        
        assert client.agent_name == "test-agent"
        assert client.agent_config == config

    def test_init_with_full_config(self):
        """Test initialization with full agent config."""
        config = {
            "name": "full-agent",
            "model": {
                "base": "Qwen/Qwen3-14B-Instruct",
                "temperature": 0.7,
                "max_tokens": 2048
            },
            "personality": "helpful"
        }
        client = AgentClient("full-agent", config)
        
        assert client.agent_name == "full-agent"
        assert client.agent_config["model"]["temperature"] == 0.7


class TestAgentClientChat:
    """Test AgentClient chat functionality."""

    def test_chat_returns_placeholder_response(self):
        """Test that chat returns a placeholder response."""
        config = {"name": "test-agent", "model": {"base": "Qwen/Qwen3-7B-Instruct"}}
        client = AgentClient("test-agent", config)
        
        response = client.chat("Hello, how are you?")
        
        assert "[AGENT RESPONSE PLACEHOLDER]" in response
        assert "test-agent" in response
        assert "Qwen/Qwen3-7B-Instruct" in response

    def test_chat_truncates_long_messages(self):
        """Test that long messages are truncated in the response."""
        config = {"name": "test-agent", "model": {"base": "Qwen/Qwen3-7B-Instruct"}}
        client = AgentClient("test-agent", config)
        
        long_message = "A" * 500  # 500 character message
        response = client.chat(long_message)
        
        # Should truncate to 100 characters
        assert "A" * 100 + "..." in response

    def test_chat_with_context(self):
        """Test chat with conversation context."""
        config = {"name": "test-agent", "model": {"base": "Qwen/Qwen3-7B-Instruct"}}
        client = AgentClient("test-agent", config)
        
        context = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]
        response = client.chat("New message", context=context)
        
        # Context is accepted but not used in placeholder
        assert "[AGENT RESPONSE PLACEHOLDER]" in response

    def test_chat_with_empty_context(self):
        """Test chat with empty context list."""
        config = {"name": "test-agent", "model": {"base": "Qwen/Qwen3-7B-Instruct"}}
        client = AgentClient("test-agent", config)
        
        response = client.chat("Hello", context=[])
        
        assert "[AGENT RESPONSE PLACEHOLDER]" in response

    def test_chat_with_none_context(self):
        """Test chat with None context (default)."""
        config = {"name": "test-agent", "model": {"base": "Qwen/Qwen3-7B-Instruct"}}
        client = AgentClient("test-agent", config)
        
        response = client.chat("Hello", context=None)
        
        assert "[AGENT RESPONSE PLACEHOLDER]" in response


class TestAgentClientEdgeCases:
    """Test edge cases and error handling."""

    def test_chat_with_empty_message(self):
        """Test chat with empty message."""
        config = {"name": "test-agent", "model": {"base": "Qwen/Qwen3-7B-Instruct"}}
        client = AgentClient("test-agent", config)
        
        response = client.chat("")
        
        assert "[AGENT RESPONSE PLACEHOLDER]" in response

    def test_chat_with_special_characters(self):
        """Test chat with special characters in message."""
        config = {"name": "test-agent", "model": {"base": "Qwen/Qwen3-7B-Instruct"}}
        client = AgentClient("test-agent", config)
        
        message = "Hello! @#$%^&*() 你好 🦞"
        response = client.chat(message)
        
        assert "[AGENT RESPONSE PLACEHOLDER]" in response

    def test_agent_config_without_model(self):
        """Test agent config without model key."""
        config = {"name": "test-agent"}
        client = AgentClient("test-agent", config)
        
        response = client.chat("Hello")
        
        assert "unknown" in response  # Default model_id

    def test_agent_config_with_empty_model(self):
        """Test agent config with empty model dict."""
        config = {"name": "test-agent", "model": {}}
        client = AgentClient("test-agent", config)
        
        response = client.chat("Hello")
        
        assert "unknown" in response  # Default model_id


class TestAgentClientModelExtraction:
    """Test model configuration extraction."""

    def test_extract_model_id_from_nested_config(self):
        """Test extracting model ID from nested config."""
        config = {
            "name": "test-agent",
            "model": {
                "base": "meta-llama/Llama-3-70B-Instruct",
                "quantization": "4bit"
            }
        }
        client = AgentClient("test-agent", config)
        response = client.chat("Test")
        
        assert "meta-llama/Llama-3-70B-Instruct" in response

    def test_extract_model_id_from_simple_config(self):
        """Test extracting model ID from simple config."""
        config = {"name": "test-agent", "model": "mistralai/Mistral-7B-Instruct"}
        client = AgentClient("test-agent", config)
        response = client.chat("Test")
        
        # Should handle both dict and string model configs
        assert "[AGENT RESPONSE PLACEHOLDER]" in response
