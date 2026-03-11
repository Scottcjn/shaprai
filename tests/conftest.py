import pytest
import shutil
from pathlib import Path

@pytest.fixture
def temp_agents_dir(tmp_path):
    """Fixture for a temporary agents directory."""
    d = tmp_path / "agents"
    d.mkdir()
    return d

@pytest.fixture
def mock_template():
    """Fixture for a basic AgentTemplate."""
    from shaprai.core.template_engine import AgentTemplate
    return AgentTemplate(
        name="test-template",
        model={"base": "test-model"},
        personality={"tone": "professional"},
        capabilities=["code_review"],
        platforms=["github"]
    )
