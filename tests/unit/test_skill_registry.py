from pathlib import Path

from agent.skills.loader import SkillMetadata
from agent.tools import skill


def test_unknown_skill_reports_only_discovered_registry_entries(monkeypatch) -> None:
    monkeypatch.setattr(
        skill,
        "discover_available_skills",
        lambda: [SkillMetadata(name="summary", description="", skill_path=Path("summary"))],
    )
    monkeypatch.setattr(skill, "build_skill_runtime_payload", lambda *_args, **_kwargs: None)

    result = skill.use_skill.func("mindmap", "生成导图")

    assert result == "Unknown skill 'mindmap'. Available skills: summary."


def test_skill_schema_does_not_advertise_a_stale_static_skill_list() -> None:
    description = skill.SkillInput.model_json_schema()["properties"]["skill_name"]["description"]

    assert "mindmap" not in description
