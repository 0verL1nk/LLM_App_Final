from dataclasses import dataclass
from typing import Callable

from .paper_prompt import build_paper_system_prompt

PromptBuilder = Callable[..., str]


@dataclass(frozen=True)
class AgentProfile:
    name: str
    description: str
    prompt_builder: PromptBuilder
    capability_ids: tuple[str, ...] = ()
    middleware_ids: tuple[str, ...] = ()


paper_leader_profile = AgentProfile(
    name="paper_leader",
    description="Leader agent for paper reading and orchestrated collaboration.",
    prompt_builder=build_paper_system_prompt,
    capability_ids=("document_pack", "planning_pack", "skill_pack", "web_pack", "human_pack", "a2ui_pack"),
    middleware_ids=("trace", "llm_logger", "subagent", "todolist", "plan"),
)
