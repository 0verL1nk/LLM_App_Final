"""Project workspace use cases with ownership enforcement."""

from typing import Any

from ..adapters.sqlite.project_repository import (
    create_project,
    create_project_session,
    delete_project_session,
    ensure_default_project_session,
    get_project_by_uid,
    list_project_files,
    list_project_session_messages_page,
    list_project_sessions,
    list_projects,
    update_project,
    update_project_session,
)


def require_project(
    *, project_uid: str, user_uuid: str, db_name: str = "./database.sqlite"
) -> dict[str, Any]:
    project = get_project_by_uid(project_uid=project_uid, uuid=user_uuid, db_name=db_name)
    if project is None:
        raise LookupError("Project not found")
    return project


def list_user_projects(*, user_uuid: str, include_archived: bool = False) -> list[dict[str, Any]]:
    return list_projects(uuid=user_uuid, include_archived=include_archived)


def create_user_project(
    *, user_uuid: str, project_name: str, description: str = ""
) -> dict[str, Any]:
    normalized_name = project_name.strip()
    if not normalized_name:
        raise ValueError("Project name is required")
    project = create_project(
        uuid=user_uuid,
        project_name=normalized_name,
        description=description.strip(),
    )
    ensure_default_project_session(project_uid=project["project_uid"], uuid=user_uuid)
    return project


def update_user_project(
    *,
    project_uid: str,
    user_uuid: str,
    project_name: str | None = None,
    description: str | None = None,
    archived: bool | None = None,
) -> dict[str, Any]:
    require_project(project_uid=project_uid, user_uuid=user_uuid)
    update_project(
        project_uid=project_uid,
        uuid=user_uuid,
        project_name=project_name,
        description=description,
        archived=int(archived) if archived is not None else None,
    )
    return require_project(project_uid=project_uid, user_uuid=user_uuid)


def list_project_documents(*, project_uid: str, user_uuid: str) -> list[dict[str, Any]]:
    require_project(project_uid=project_uid, user_uuid=user_uuid)
    return list_project_files(project_uid=project_uid, uuid=user_uuid, active_only=False)


def list_workspace_sessions(*, project_uid: str, user_uuid: str) -> list[dict[str, Any]]:
    require_project(project_uid=project_uid, user_uuid=user_uuid)
    sessions = list_project_sessions(project_uid=project_uid, uuid=user_uuid)
    if not sessions:
        ensure_default_project_session(project_uid=project_uid, uuid=user_uuid)
        sessions = list_project_sessions(project_uid=project_uid, uuid=user_uuid)
    return sessions


def create_workspace_session(
    *, project_uid: str, user_uuid: str, session_name: str, parent_session_uid: str | None = None
) -> dict[str, Any]:
    require_project(project_uid=project_uid, user_uuid=user_uuid)
    sessions = list_workspace_sessions(project_uid=project_uid, user_uuid=user_uuid)
    main_session = next((item for item in sessions if item.get("is_main")), sessions[0])
    parent = parent_session_uid or str(main_session["session_uid"])
    if not any(str(item["session_uid"]) == parent for item in sessions):
        raise LookupError("Parent session not found")
    return create_project_session(
        project_uid=project_uid,
        uuid=user_uuid,
        session_name=session_name.strip() or "新会话",
        parent_session_uid=parent,
    )


def update_workspace_session(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    session_name: str | None,
    is_pinned: bool | None,
) -> None:
    require_project(project_uid=project_uid, user_uuid=user_uuid)
    changed = update_project_session(
        session_uid=session_uid,
        project_uid=project_uid,
        uuid=user_uuid,
        session_name=session_name,
        is_pinned=int(is_pinned) if is_pinned is not None else None,
    )
    if not changed:
        raise LookupError("Session not found")


def delete_workspace_session(*, project_uid: str, session_uid: str, user_uuid: str) -> None:
    sessions = list_workspace_sessions(project_uid=project_uid, user_uuid=user_uuid)
    if len(sessions) <= 1:
        raise ValueError("A project must keep at least one session")
    deleted = delete_project_session(
        session_uid=session_uid,
        project_uid=project_uid,
        uuid=user_uuid,
    )
    if not deleted:
        raise LookupError("Session not found")


def list_workspace_messages(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    offset: int,
    limit: int,
) -> list[dict[str, Any]]:
    require_project(project_uid=project_uid, user_uuid=user_uuid)
    return list_project_session_messages_page(
        session_uid=session_uid,
        project_uid=project_uid,
        uuid=user_uuid,
        offset=offset,
        limit=limit,
    )


__all__ = [
    "create_user_project",
    "create_workspace_session",
    "delete_workspace_session",
    "list_project_documents",
    "list_user_projects",
    "list_workspace_messages",
    "list_workspace_sessions",
    "require_project",
    "update_user_project",
    "update_workspace_session",
]
