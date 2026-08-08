import asyncio
import json
import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse

from agent.adapters.paddle_ocr import document_conversion_capability
from agent.adapters.sqlite.rag_ingestion_repository import (
    get_ingestion,
    list_project_ingestions,
)
from agent.adapters.sqlite.run_repository import (
    expire_stalled_runs,
    get_run,
    list_run_events,
    list_session_runs,
)
from agent.application.document_library import upload_project_document
from agent.application.rag_ingestion import (
    enqueue_document_ingestion,
    reconcile_project_ingestions,
)
from agent.application.research_workspace import research_workspace_service
from agent.application.user_configuration import (
    read_user_configuration,
    save_user_configuration,
)
from agent.application.workspace import (
    create_user_project,
    create_workspace_session,
    delete_workspace_session,
    list_project_documents,
    list_user_projects,
    list_workspace_messages,
    list_workspace_sessions,
    require_project,
    update_user_project,
    update_workspace_session,
)
from agent.settings import load_agent_settings
from utils.task_queue import enqueue_background_task, get_job_status

from .dependencies import current_user_id
from .schemas import (
    ProjectCreate,
    ProjectUpdate,
    RunCreate,
    SessionCreate,
    SessionUpdate,
    SettingsUpdate,
    TurnCreate,
)

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)
UserId = Annotated[str, Depends(current_user_id)]


def _not_found(exc: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _preview_page_path(*, file_path: Path, stored_doc_uid: str, page_no: int) -> Path:
    """Build an OCR preview path from the owned document record."""
    if Path(stored_doc_uid).name != stored_doc_uid:
        raise HTTPException(status_code=404, detail="Preview page not found")
    preview_root = (file_path.parent / "previews").resolve()
    document_preview_root = (preview_root / stored_doc_uid).resolve()
    preview_path = (document_preview_root / f"page-{page_no:05d}.png").resolve()
    if not document_preview_root.is_relative_to(preview_root) or not preview_path.is_relative_to(document_preview_root):
        raise HTTPException(status_code=404, detail="Preview page not found")
    return preview_path


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/document-conversion")
def document_conversion(_user_uuid: UserId) -> dict[str, Any]:
    """Expose local Office preview readiness without disclosing host paths."""
    return {"data": document_conversion_capability()}


@router.get("/projects")
def projects(user_uuid: UserId, include_archived: bool = False) -> dict[str, Any]:
    return {"data": list_user_projects(user_uuid=user_uuid, include_archived=include_archived)}


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate, user_uuid: UserId) -> dict[str, Any]:
    return {"data": create_user_project(user_uuid=user_uuid, **payload.model_dump())}


@router.get("/projects/{project_uid}")
def project_detail(project_uid: str, user_uuid: UserId) -> dict[str, Any]:
    try:
        return {"data": require_project(project_uid=project_uid, user_uuid=user_uuid)}
    except LookupError as exc:
        raise _not_found(exc) from exc


@router.patch("/projects/{project_uid}")
def patch_project(project_uid: str, payload: ProjectUpdate, user_uuid: UserId) -> dict[str, Any]:
    try:
        return {
            "data": update_user_project(
                project_uid=project_uid,
                user_uuid=user_uuid,
                **payload.model_dump(),
            )
        }
    except LookupError as exc:
        raise _not_found(exc) from exc


@router.get("/projects/{project_uid}/documents")
def documents(project_uid: str, user_uuid: UserId) -> dict[str, Any]:
    try:
        docs = list_project_documents(project_uid=project_uid, user_uuid=user_uuid)
    except LookupError as exc:
        raise _not_found(exc) from exc
    ingestion_rows = list_project_ingestions(project_uid=project_uid, uuid=user_uuid)
    reconcile_project_ingestions(
        project_uid=project_uid,
        user_uuid=user_uuid,
        documents=docs,
        ingestions=ingestion_rows,
        get_job_status_fn=get_job_status,
        enqueue_background_fn=enqueue_background_task,
    )
    ingestion_rows = list_project_ingestions(project_uid=project_uid, uuid=user_uuid)
    statuses = {str(item.get("doc_uid") or ""): item for item in ingestion_rows}
    return {
        "data": [{**item, "ingestion": statuses.get(str(item.get("uid") or ""))} for item in docs]
    }


@router.post("/projects/{project_uid}/documents", status_code=202)
async def upload_document(
    project_uid: str,
    user_uuid: UserId,
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    content = await file.read()
    try:
        result = await run_in_threadpool(
            upload_project_document,
            project_uid=project_uid,
            user_uuid=user_uuid,
            file_name=file.filename or "document",
            content=content,
            enqueue_background_fn=enqueue_background_task,
        )
    except LookupError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": result}


@router.post("/projects/{project_uid}/documents/{doc_uid}/retry", status_code=202)
def retry_document(project_uid: str, doc_uid: str, user_uuid: UserId) -> dict[str, Any]:
    ingestion = get_ingestion(project_uid=project_uid, doc_uid=doc_uid, uuid=user_uuid)
    if ingestion is None:
        raise HTTPException(status_code=404, detail="Document ingestion not found")
    queued = enqueue_document_ingestion(
        project_uid=project_uid,
        doc_uid=doc_uid,
        user_uuid=user_uuid,
        doc_name=str(ingestion.get("doc_name") or doc_uid),
        file_path=str(ingestion.get("file_path") or ""),
        enqueue_background_fn=enqueue_background_task,
        force=True,
    )
    return {"data": queued}


@router.get("/projects/{project_uid}/documents/{doc_uid}/preview/{page_no}")
def document_preview_page(project_uid: str, doc_uid: str, page_no: int, user_uuid: UserId) -> FileResponse:
    """Serve only an owned document's OCR-rendered page image."""
    if page_no < 1:
        raise HTTPException(status_code=404, detail="Preview page not found")
    documents = list_project_documents(project_uid=project_uid, user_uuid=user_uuid)
    document = next((item for item in documents if str(item.get("uid")) == doc_uid), None)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = Path(str(document.get("file_path") or "")).resolve()
    stored_doc_uid = str(document.get("uid") or "")
    preview_path = _preview_page_path(
        file_path=file_path,
        stored_doc_uid=stored_doc_uid,
        page_no=page_no,
    )
    if not preview_path.is_file():
        raise HTTPException(status_code=404, detail="Preview is not ready; retry document processing")
    return FileResponse(preview_path, media_type="image/png")


@router.get("/projects/{project_uid}/sessions")
def sessions(project_uid: str, user_uuid: UserId) -> dict[str, Any]:
    try:
        return {"data": list_workspace_sessions(project_uid=project_uid, user_uuid=user_uuid)}
    except LookupError as exc:
        raise _not_found(exc) from exc


@router.post("/projects/{project_uid}/sessions", status_code=201)
def create_session(project_uid: str, payload: SessionCreate, user_uuid: UserId) -> dict[str, Any]:
    try:
        return {
            "data": create_workspace_session(
                project_uid=project_uid,
                user_uuid=user_uuid,
                session_name=payload.session_name,
                parent_session_uid=payload.parent_session_uid,
            )
        }
    except LookupError as exc:
        raise _not_found(exc) from exc


@router.patch("/projects/{project_uid}/sessions/{session_uid}", status_code=204)
def patch_session(
    project_uid: str,
    session_uid: str,
    payload: SessionUpdate,
    user_uuid: UserId,
) -> None:
    try:
        update_workspace_session(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            **payload.model_dump(),
        )
    except LookupError as exc:
        raise _not_found(exc) from exc


@router.delete("/projects/{project_uid}/sessions/{session_uid}", status_code=204)
def delete_session(project_uid: str, session_uid: str, user_uuid: UserId) -> None:
    try:
        delete_workspace_session(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
        )
    except LookupError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/projects/{project_uid}/sessions/{session_uid}/messages")
def messages(
    project_uid: str,
    session_uid: str,
    user_uuid: UserId,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, Any]:
    try:
        return {
            "data": list_workspace_messages(
                project_uid=project_uid,
                session_uid=session_uid,
                user_uuid=user_uuid,
                offset=offset,
                limit=limit,
            )
        }
    except LookupError as exc:
        raise _not_found(exc) from exc


@router.post("/projects/{project_uid}/sessions/{session_uid}/turns")
async def execute_turn(
    project_uid: str,
    session_uid: str,
    payload: TurnCreate,
    user_uuid: UserId,
) -> dict[str, Any]:
    try:
        result = await run_in_threadpool(
            research_workspace_service.execute_turn,
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            prompt=payload.prompt,
        )
    except LookupError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Agent turn failed: user=%s project=%s session=%s",
            user_uuid,
            project_uid,
            session_uid,
        )
        raise HTTPException(status_code=502, detail="Model execution failed") from exc
    return {"data": result}


@router.post("/projects/{project_uid}/sessions/{session_uid}/runs", status_code=202)
def create_agent_run(
    project_uid: str,
    session_uid: str,
    payload: RunCreate,
    user_uuid: UserId,
) -> dict[str, Any]:
    try:
        run = research_workspace_service.prepare_turn_run(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            prompt=payload.prompt,
            client_request_id=payload.client_request_id,
            enqueue_background_fn=enqueue_background_task,
        )
    except LookupError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    run_uid = str(run["run_uid"])
    return {
        "data": {
            "run_id": run_uid,
            "status": run["status"],
            "stream_url": f"/api/v1/runs/{run_uid}/events",
        }
    }


@router.get("/projects/{project_uid}/sessions/{session_uid}/runs")
def list_resumable_agent_runs(
    project_uid: str,
    session_uid: str,
    user_uuid: UserId,
) -> dict[str, Any]:
    try:
        require_project(project_uid=project_uid, user_uuid=user_uuid)
    except LookupError as exc:
        raise _not_found(exc) from exc
    expire_stalled_runs(
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid=user_uuid,
        max_idle_seconds=load_agent_settings().agent_llm_request_timeout + 30,
    )
    return {
        "data": list_session_runs(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
        )
    }


@router.get("/runs/{run_uid}")
def read_agent_run(run_uid: str, user_uuid: UserId) -> dict[str, Any]:
    run = get_run(run_uid=run_uid, user_uuid=user_uuid)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"data": run}


@router.get("/runs/{run_uid}/events")
async def stream_agent_run_events(
    run_uid: str,
    user_uuid: UserId,
    after_sequence: Annotated[int, Query(alias="afterSeq", ge=0)] = 0,
) -> StreamingResponse:
    run = get_run(run_uid=run_uid, user_uuid=user_uuid)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_stream():
        sequence = after_sequence
        heartbeat_at = asyncio.get_running_loop().time()
        while True:
            events = await run_in_threadpool(
                list_run_events,
                run_uid=run_uid,
                after_sequence=sequence,
            )
            for event in events:
                sequence = int(event["sequence"])
                yield (
                    f"id: {event['eventId']}\n"
                    f"event: {event['eventType']}\n"
                    f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                )
            current = await run_in_threadpool(get_run, run_uid=run_uid, user_uuid=user_uuid)
            if current is None or (current["status"] in {"completed", "failed", "cancelled"} and not events):
                break
            now = asyncio.get_running_loop().time()
            if now - heartbeat_at >= 15:
                await run_in_threadpool(
                    expire_stalled_runs,
                    project_uid=str(run["project_uid"]),
                    session_uid=str(run["session_uid"]),
                    user_uuid=user_uuid,
                    max_idle_seconds=load_agent_settings().agent_llm_request_timeout + 30,
                )
                yield ": ping\n\n"
                heartbeat_at = now
            await asyncio.sleep(0.25)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/settings")
def settings(user_uuid: UserId) -> dict[str, Any]:
    return {"data": read_user_configuration(user_uuid=user_uuid)}


@router.put("/settings")
def update_settings(payload: SettingsUpdate, user_uuid: UserId) -> dict[str, Any]:
    saved = save_user_configuration(user_uuid=user_uuid, **payload.model_dump())
    research_workspace_service.invalidate_user(user_uuid)
    return {"data": saved}
