"""
FastAPI application entry point for Literature Reading Assistant Backend
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.logger import get_logger, log_request
from core.rate_limit import RateLimitMiddleware
from api.routers import auth
from api.routers import files
from api.routers import documents
from api.routers import tasks
from api.routers import users
from api.routers import statistics
from api import websocket
from api.errors import setup_exception_handlers

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
    from db.database import engine
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
        from background_tasks.task_queue import redis_conn

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


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": f"Welcome to {settings.project_name} API",
        "version": "1.0.0",
        "docs": f"{settings.api_v1_str}/docs",
        "health": "/health",
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8501,
        reload=False,  # Set to False for simpler startup
        log_level=settings.log_level.lower(),
    )
