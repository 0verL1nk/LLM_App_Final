"""Scholarly graph traversal and library ingestion tools for research subagents."""

import logging
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field

from ..scholarly_search import (
    ScholarlySearchError,
    download_paper_pdf,
    fetch_semantic_scholar_citations,
    format_search_papers_results,
)

logger = logging.getLogger(__name__)

_INGESTION_POLL_HINT = (
    "Retrieval becomes available after ingestion completes; check with list_document."
)


class GetPaperCitationsInput(BaseModel):
    paper_id: str = Field(description="Semantic Scholar PaperId from a previous search_papers result.")
    direction: str = Field(
        default="citations",
        description="Edge direction: citations (papers citing this one) or references (papers this one cites).",
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum neighbours to return.")


class AddPaperToLibraryInput(BaseModel):
    url: str = Field(description="Direct PDF URL of an open-access paper (openAccessPdf URL preferred).")
    title: str = Field(min_length=1, max_length=300, description="Paper title used as the document file name.")
    # Injected args live in the schema so the ToolNode both injects them and
    # hides them from the model-facing contract (same lesson as update_plan).
    tool_call_id: Annotated[str, InjectedToolCallId] = ""
    state: Annotated[dict[str, Any], InjectedState] = Field(default_factory=dict)


@tool(
    "get_paper_citations",
    description="Traverse the Semantic Scholar citation graph one hop for snowballing literature search.",
    args_schema=GetPaperCitationsInput,
)
def get_paper_citations(paper_id: str, direction: str = "citations", limit: int = 10) -> str:
    normalized_direction = direction.strip().lower()
    if normalized_direction not in {"citations", "references"}:
        return "Direction must be 'citations' or 'references'."
    logger.info(
        "tool.get_paper_citations called: direction=%s limit=%s", normalized_direction, limit
    )
    try:
        papers = fetch_semantic_scholar_citations(
            paper_id,
            direction=normalized_direction,  # type: ignore[arg-type]
            limit=limit,
        )
    except ScholarlySearchError as exc:
        logger.warning("tool.get_paper_citations failed: %s", exc)
        return f"Citation lookup failed: {exc}"
    return format_search_papers_results(papers)


def build_add_paper_to_library_tool(*, project_uid: str, user_uuid: str) -> BaseTool:
    """Bind one project library target so the model only supplies url + title."""

    @tool(
        "add_paper_to_library",
        description=(
            "Download one open-access paper PDF and ingest it into the project library "
            "so later evidence retrieval can quote it. Use only URLs from search results."
        ),
        args_schema=AddPaperToLibraryInput,
    )
    def add_paper_to_library(
        url: str,
        title: str,
        tool_call_id: Annotated[str, InjectedToolCallId] = "",
        state: Annotated[dict[str, Any], InjectedState] = None,
    ):
        """Ingest one paper PDF; returns a Command so the result stays in message flow."""
        from langgraph.types import Command

        from ..application.document_library import upload_project_document
        from utils.task_queue import enqueue_background_task

        safe_title = " ".join(title.split())[:200] or "paper"
        file_name = f"{safe_title}.pdf"
        logger.info("tool.add_paper_to_library called: title_len=%s", len(safe_title))
        try:
            content = download_paper_pdf(url)
        except ScholarlySearchError as exc:
            logger.warning("tool.add_paper_to_library download failed: %s", exc)
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            f"Paper download failed: {exc}",
                            tool_call_id=tool_call_id,
                            status="error",
                        )
                    ]
                }
            )
        try:
            result = upload_project_document(
                project_uid=project_uid,
                user_uuid=user_uuid,
                file_name=file_name,
                content=content,
                enqueue_background_fn=enqueue_background_task,
            )
        except ValueError as exc:
            logger.warning("tool.add_paper_to_library rejected: %s", exc)
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            f"Paper rejected by the library: {exc}",
                            tool_call_id=tool_call_id,
                            status="error",
                        )
                    ]
                }
            )
        doc_uid = str(result.get("uid") or result.get("doc_uid") or "")
        doc_name = str(result.get("file_name") or file_name)
        logger.info("tool.add_paper_to_library success: doc_uid=%s", doc_uid)
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Paper queued for ingestion into the project library: {doc_name} (uid={doc_uid}). {_INGESTION_POLL_HINT}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )

    return add_paper_to_library


__all__ = ["build_add_paper_to_library_tool", "get_paper_citations"]
