import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent.application.research_workspace import research_workspace_service

from .routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    research_workspace_service.close()


app = FastAPI(title="PaperSage API", version="1.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
WEB_DIST = RESOURCE_ROOT / "web" / "dist"
ROOT_STATIC_FILES = {"favicon.svg", "icons.svg", "papersage-mark.svg"}
if (WEB_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa_fallback(path: str) -> FileResponse:
    if path in ROOT_STATIC_FILES:
        candidate = WEB_DIST / path
        if candidate.is_file():
            return FileResponse(candidate)
    if path == "index.html":
        candidate = WEB_DIST / "index.html"
        if candidate.is_file():
            return FileResponse(candidate)
    return FileResponse(WEB_DIST / "index.html")


def run() -> None:
    uvicorn.run("api.main:app", host="127.0.0.1", port=int(os.getenv("PAPERSAGE_PORT", "8000")), reload=False)


if __name__ == "__main__":
    run()
