import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CARD_PATH = ROOT / "agent-card.json"
SCORE_AREAS = {
    "goal_clarity",
    "tool_permissions",
    "memory",
    "evals",
    "failure_handling",
    "security",
    "observability",
    "cost_control",
    "human_review",
    "documentation",
}
TOOL_SOURCES = {
    "search_document": "agent/tools/document.py",
    "list_document": "agent/tools/document.py",
    "read_document": "agent/tools/document.py",
    "search_web": "agent/tools/web_search.py",
    "search_papers": "agent/tools/paper_search.py",
    "use_skill": "agent/tools/skill.py",
    "update_plan": "agent/tools/plan_tools.py",
    "delegate_task": "agent/middlewares/durable_delegation.py",
    "ask_human": "agent/capabilities/human.py",
    "add_paper_to_library": "agent/tools/paper_library.py",
}


def _card() -> dict:
    return json.loads(CARD_PATH.read_text(encoding="utf-8"))


def test_agent_card_is_fail_visible_and_score_complete() -> None:
    card = _card()

    assert card["$schema"].endswith(
        "/awesome-agentic-engineering/v0.15.0/schema/agent-card.schema.json"
    )
    assert card["risk_profile"] == "draft-only"
    assert set(card["scorecard"]) == SCORE_AREAS
    assert all(score in {0, 1, 2} for score in card["scorecard"].values())
    assert sum(card["scorecard"].values()) == 18
    assert len(card["launch_blockers"]) == 3
    assert all(blocker.strip() for blocker in card["launch_blockers"])


def test_agent_card_declares_only_read_or_draft_tool_effects() -> None:
    tools = _card()["tools"]

    assert {tool["name"] for tool in tools} == set(TOOL_SOURCES)
    assert len({tool["name"] for tool in tools}) == len(tools)
    assert {tool["effect"] for tool in tools} == {"read_only", "draft"}
    assert all(tool["effect"] != "external_state" for tool in tools)
    assert all(isinstance(tool["approval_required"], bool) for tool in tools)


def test_agent_card_tool_names_and_fixture_references_exist() -> None:
    card = _card()

    for tool_name, relative_path in TOOL_SOURCES.items():
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert tool_name in source
    for fixture in card["eval_fixtures"]:
        assert (ROOT / fixture).is_file()
