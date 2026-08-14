from typing import Any

from ..tools.plan_tools import read_plan, update_plan


def build_planning_tools(_deps: Any) -> list[Any]:
    return [update_plan, read_plan]
