import pytest
import yaml
from pathlib import Path
from shaprai.core.template_engine import AgentTemplate, load_template, save_template, fork_template, list_templates

def test_agent_template_defaults():
    template = AgentTemplate(name="test")
    assert template.name == "test"
    assert template.ethics_profile == "sophiacore_default"
    assert template.driftlock["enabled"] is True
    assert template.version == "1.0"

def test_save_and_load_template(tmp_path):
    template_path = tmp_path / "test_template.yaml"
    template = AgentTemplate(
        name="custom-agent",
        personality={"humor": "high"},
        capabilities=["chat"]
    )
    
    save_template(template, str(template_path))
    assert template_path.exists()
    
    loaded = load_template(str(template_path))
    assert loaded.name == "custom-agent"
    assert loaded.personality["humor"] == "high"
    assert "chat" in loaded.capabilities

def test_load_template_not_found():
    with pytest.raises(FileNotFoundError):
        load_template("non_existent.yaml")

def test_fork_template(tmp_path):
    source_path = tmp_path / "source.yaml"
    source = AgentTemplate(name="source", personality={"tone": "calm"})
    save_template(source, str(source_path))
    
    forked = fork_template(str(source_path), "forked", overrides={"personality": {"tone": "energetic"}})
    assert forked.name == "forked"
    assert forked.personality["tone"] == "energetic"

def test_list_templates(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    
    t1 = AgentTemplate(name="t1")
    t2 = AgentTemplate(name="t2")
    
    save_template(t1, str(templates_dir / "t1.yaml"))
    save_template(t2, str(templates_dir / "t2.yaml"))
    (templates_dir / "invalid.txt").write_text("not a yaml")
    
    templates = list_templates(str(templates_dir))
    assert len(templates) == 2
    assert {t.name for t in templates} == {"t1", "t2"}

def test_list_templates_malformed(tmp_path):
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "bad.yaml").write_text(":") # Invalid YAML
    
    templates = list_templates(str(templates_dir))
    assert len(templates) == 0

def test_save_template_creates_dir(tmp_path):
    nested_path = tmp_path / "a" / "b" / "template.yaml"
    template = AgentTemplate(name="nested")
    save_template(template, str(nested_path))
    assert nested_path.exists()
