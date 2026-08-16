"""Scholarly search, citation traversal, and library ingestion capability."""

from typing import Any

from ..tools.paper_library import build_add_paper_to_library_tool, get_paper_citations
from ..tools.paper_search import search_papers


def build_paper_tools(deps: Any) -> list[Any]:
    project_uid = str(getattr(deps, "project_uid", "") or "").strip()
    user_uuid = str(getattr(deps, "user_uuid", "") or "").strip()
    tools: list[Any] = [search_papers, get_paper_citations]
    if project_uid and user_uuid:
        tools.append(build_add_paper_to_library_tool(project_uid=project_uid, user_uuid=user_uuid))
    return tools
