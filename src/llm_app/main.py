"""
FastAPI application entry point for Literature Reading Assistant Backend
"""

import sys
from pathlib import Path
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from llm_app.core.config import settings
from llm_app.core.logger import get_logger, log_request
from llm_app.core.rate_limit import RateLimitMiddleware
from llm_app.api.routers import auth
from llm_app.api.routers import files
from llm_app.api.routers import documents
from llm_app.api.routers import tasks
from llm_app.api.routers import users
from llm_app.api.routers import statistics
from llm_app.api import websocket
from llm_app.api.errors import setup_exception_handlers

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info(f"Starting {settings.project_name}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"API version: {settings.api_v1_str}")
    yield
    # Shutdown
    logger.info("Shutting down application")


# Create FastAPI application
app = FastAPI(
    title=settings.project_name,
    description="AI-powered literature reading assistant API",
    version="1.0.0",
    docs_url=f"{settings.api_v1_str}/docs",
    redoc_url=f"{settings.api_v1_str}/redoc",
    openapi_url=f"{settings.api_v1_str}/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)


# Request logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all HTTP requests"""
    start_time = time.time()

    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Process request
    response = await call_next(request)

    # Calculate response time
    process_time = time.time() - start_time

    # Log request
    request_data = {
        "method": request.method,
        "url": str(request.url),
        "client": client_ip,
    }

    log_request(logger, request_data, response.status_code, process_time)

    # Add timing header
    response.headers["X-Process-Time"] = str(process_time)

    return response


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    from llm_app.db.database import engine
    from sqlalchemy import text

    checks = {
        "api": "healthy",
        "database": "unknown",
        "redis": "unknown",
    }

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unhealthy"

    try:
        from llm_app.background_tasks.task_queue import redis_conn

        if redis_conn:
            redis_conn.ping()
            checks["redis"] = "healthy"
        else:
            checks["redis"] = "not_configured"
    except Exception:
        checks["redis"] = "unhealthy"

    overall_status = "healthy" if checks["database"] == "healthy" else "degraded"

    return {
        "status": overall_status,
        "version": "1.0.0",
        "project": settings.project_name,
        "checks": checks,
    }


# Register API routers
app.include_router(auth.router, prefix=settings.api_v1_str)
app.include_router(
    files.router,
    prefix=settings.api_v1_str,
)
app.include_router(
    documents.router,
    prefix=settings.api_v1_str,
)
app.include_router(
    tasks.router,
    prefix=settings.api_v1_str,
)
app.include_router(
    users.router,
    prefix=settings.api_v1_str,
)
app.include_router(
    statistics.router,
    prefix=settings.api_v1_str,
)
app.include_router(websocket.router, prefix=settings.api_v1_str)

setup_exception_handlers(app)

# Serve Static Files (Frontend)
static_dir = Path(__file__).parent / "static"

if static_dir.exists():
    # Mount assets directory (Vite usually outputs assets to assets/)
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Catch-all route for SPA
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Ignore API routes (let them be handled by 404 handler if not matched above)
        # But wait, routes above match first. If we are here, it's not a registered API route.
        # Ensure we don't capture /api/v1/... requests that 404'd
        if full_path.startswith(settings.api_v1_str.lstrip("/")):
             return JSONResponse(status_code=404, content={"detail": "Not Found"})

        # Try to serve file directly
        file_path = static_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)

        # Serve index.html for everything else (SPA routing)
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        return JSONResponse(status_code=404, content={"detail": "Frontend not found"})


def start():
    """Entry point for CLI"""
    import os
    import uvicorn
    import webbrowser
    import threading
    import time

    # Configuration from environment variables
    port = int(os.environ.get("LLM_APP_PORT", "8501"))
    host = os.environ.get("LLM_APP_HOST", "0.0.0.0")
    no_browser = os.environ.get("LLM_APP_NO_BROWSER", "").lower() in ("true", "1", "yes")

    def open_browser():
        if not no_browser:
            time.sleep(1.5)  # Wait for server to start
            webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=open_browser, daemon=True).start()

    # Use reload=False for production/package
    uvicorn.run("llm_app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    start()