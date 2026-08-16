"""Model-generated follow-up suggestions for research sessions."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from agent.application.session_suggestions import generate_session_suggestions
from agent.application.workspace import list_project_documents, list_workspace_messages

from .dependencies import current_user_id

suggestion_router = APIRouter()
UserId = Annotated[str, Depends(current_user_id)]


@suggestion_router.get("/projects/{project_uid}/sessions/{session_uid}/suggestions")
def read_session_suggestions(
    project_uid: str,
    session_uid: str,
    user_uuid: UserId,
) -> dict[str, Any]:
    """Model-generated follow-up prompts grounded in the session's state."""
    messages = list_workspace_messages(
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid=user_uuid,
        offset=0,
        limit=200,
    )
    documents = list_project_documents(project_uid=project_uid, user_uuid=user_uuid)
    document_names = [
        name
        for name in (
            str(item.get("file_name") or item.get("name") or item.get("doc_name") or "").strip()
            for item in documents
        )
        if name
    ]
    return {
        "suggestions": generate_session_suggestions(
            user_uuid=user_uuid,
            project_uid=project_uid,
            session_uid=session_uid,
            messages=messages,
            document_names=document_names[:12],
        )
    }
