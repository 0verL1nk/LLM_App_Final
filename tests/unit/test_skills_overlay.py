from pathlib import Path

from agent.skills.loader import SkillLoader


def _write_skill(base: Path, name: str, description: str, *, body: str = "指引内容") -> Path:
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return skill_dir


def test_user_layer_overrides_bundled_skills_by_name(tmp_path: Path) -> None:
    bundled = tmp_path / "bundled"
    user = tmp_path / "user"
    _write_skill(bundled, "summary", "bundled summary")
    _write_skill(bundled, "translation", "bundled translation")
    _write_skill(user, "summary", "user override")
    _write_skill(user, "custom_flow", "user-only skill")
    loader = SkillLoader(skills_dir=bundled, user_skills_dir=user)

    discovered = {meta.name: meta for meta in loader.discover_skills()}
    assert set(discovered) == {"summary", "translation", "custom_flow"}
    assert discovered["summary"].description == "user override"

    assert loader.get_skill("summary").description == "user override"
    assert loader.get_skill("translation").description == "bundled translation"
    assert loader.get_skill("custom_flow") is not None
    assert loader.get_skill("missing") is None


def test_missing_user_layer_keeps_bundled_skills(tmp_path: Path) -> None:
    bundled = tmp_path / "bundled"
    _write_skill(bundled, "summary", "desc")
    loader = SkillLoader(skills_dir=bundled, user_skills_dir=tmp_path / "absent")

    assert [meta.name for meta in loader.discover_skills()] == ["summary"]
    # Discovery is re-runnable: the per-name dedup must not eat later calls.
    assert [meta.name for meta in loader.discover_skills()] == ["summary"]
    assert loader.get_skill("summary") is not None


def test_default_user_layer_resolves_from_cwd_or_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    assert SkillLoader().user_skills_dir == tmp_path / "skills"

    monkeypatch.setenv("PAPERSAGE_USER_SKILLS_DIR", str(tmp_path / "custom"))
    assert SkillLoader().user_skills_dir == tmp_path / "custom"
