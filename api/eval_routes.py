"""HTTP contract for in-app task-completion eval runs with progress polling."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent.application.evals.run_service import (
    DEFAULT_FIXTURE_PATH,
    TaskCompletionEvalService,
    task_completion_eval_service,
)

eval_router = APIRouter(prefix="/evals/task-completion", tags=["evals"])


class EvalStartRequest(BaseModel):
    fixture_path: str = Field(default=DEFAULT_FIXTURE_PATH)
    case_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=0, ge=0)
    trials: int = Field(default=1, ge=1, le=5)


def _service() -> TaskCompletionEvalService:
    return task_completion_eval_service


@eval_router.post("/start")
def start_eval_run(request: EvalStartRequest) -> dict[str, Any]:
    try:
        return {"data": _service().start(
            fixture_path=request.fixture_path,
            case_ids=request.case_ids or None,
            limit=request.limit or None,
            trials=request.trials,
        )}
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@eval_router.get("/runs")
def list_eval_runs() -> dict[str, Any]:
    return {"data": _service().list_runs()}


@eval_router.get("/runs/{uid}")
def get_eval_run(uid: str) -> dict[str, Any]:
    try:
        return {"data": _service().get(uid)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
