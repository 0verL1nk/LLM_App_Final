"""
Documents API router for text extraction and document processing.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_current_user
from models.user import User
from models.file import File
from models.task import Task
from services.task_service import TaskService
from services.file_service import FileService
from schemas.task import (
    TaskStatusResponse,
    ExtractionRequest,
    ExtractionResult,
    TaskType,
    TaskStatus,
)
from schemas.document import (
    SummarizeRequest,
    SummarizeResult,
    QARequest,
    QAResponse,
    RewriteRequest,
    RewriteResult,
    MindmapRequest,
    MindmapResult,
)
from core.logger import get_logger
from core.exceptions import APIException
from background_tasks.tasks import extract_document_task, summarize_document_task
from background_tasks.task_queue import task_queue

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


async def run_extraction_task(
    task_id: str,
    file_id: str,
    file_path: str,
    user_uuid: str,
    options: Dict[str, Any],
    db: AsyncSession,
):
    """Background task runner for extraction"""
    task_service = TaskService(db)

    try:
        # Update status to processing
        await task_service.update_task_status(
            task_id=task_id,
            status="processing",
            progress=10,
        )

        # Run extraction
        result = extract_document_task(
            task_id=task_id,
            file_id=file_id,
            file_path=file_path,
            user_uuid=user_uuid,
            options=options,
        )

        # Update with result
        await task_service.update_task_status(
            task_id=task_id,
            status="completed",
            progress=100,
            result=result,
        )

        # Update file with extracted text
        file_service = FileService(db)
        await file_service.update_file_content(
            file_id=file_id,
            user_uuid=user_uuid,
            extracted_text=result.get("text"),
            word_count=result.get("metadata", {}).get("word_count"),
        )

    except Exception as e:
        logger.error(f"Extraction task {task_id} failed: {e}")
        await task_service.update_task_status(
            task_id=task_id,
            status="failed",
            error_message=str(e),
        )


@router.post(
    "/{file_id}/extract",
    response_model=Dict[str, Any],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Extract text from document",
    description="Start async text extraction task for a document",
)
async def extract_document(
    file_id: str,
    request: Optional[ExtractionRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Extract text from an uploaded document.

    This starts an async task that:
    - Extracts text using textract
    - Splits text into sections
    - Extracts document metadata

    Returns a task_id that can be used to poll for status.
    """
    task_service = TaskService(db)
    file_service = FileService(db)

    # Check if file exists
    file = await file_service.get_file(file_id, current_user.uuid)
    if not file:
        raise APIException(
            error_code="FILE_NOT_FOUND",
            message=f"文件不存在: {file_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Check for existing completed extraction
    existing_task = await task_service.get_existing_extraction(
        file_id=file_id,
        user_uuid=current_user.uuid,
    )

    if existing_task and existing_task.result:
        return {
            "success": True,
            "data": {
                "task_id": existing_task.task_id,
                "status": existing_task.status,
                "result": existing_task.result,
            },
            "message": "已有提取结果",
        }

    # Create new task
    options = request.model_dump() if request else {}
    task = await task_service.create_task(
        user_uuid=current_user.uuid,
        file_id=file_id,
        task_type="extract",
        options=options,
    )

    # Enqueue to RQ if available, otherwise run in background
    try:
        job = task_queue.enqueue(
            extract_document_task,
            task_id=task.task_id,
            file_id=file_id,
            file_path=file.file_path,
            user_uuid=current_user.uuid,
            options=options,
        )
        await task_service.update_task_status(
            task_id=task.task_id,
            job_id=job.id,
        )
        logger.info(f"Enqueued extraction task {task.task_id} as job {job.id}")
    except Exception as e:
        logger.warning(f"RQ not available, running in background: {e}")
        # Fallback: run directly (blocking for now, TODO: use FastAPI BackgroundTasks)
        try:
            result = extract_document_task(
                task_id=task.task_id,
                file_id=file_id,
                file_path=file.file_path,
                user_uuid=current_user.uuid,
                options=options,
            )
            await task_service.update_task_status(
                task_id=task.task_id,
                status="completed",
                progress=100,
                result=result,
            )
            # Update file with extracted text
            await file_service.update_file_content(
                file_id=file_id,
                user_uuid=current_user.uuid,
                extracted_text=result.get("text"),
                word_count=result.get("metadata", {}).get("word_count"),
            )
        except Exception as ex:
            await task_service.update_task_status(
                task_id=task.task_id,
                status="failed",
                error_message=str(ex),
            )

    return {
        "success": True,
        "data": {
            "task_id": task.task_id,
            "file_id": file_id,
            "task_type": "extract",
            "status": task.status,
        },
        "message": "文本提取任务已创建",
    }


@router.get(
    "/{file_id}/extraction",
    response_model=Dict[str, Any],
    summary="Get extraction result",
    description="Get the text extraction result for a document",
)
async def get_extraction_result(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the extraction result for a document.

    Returns the extracted text, sections, and metadata if available.
    """
    task_service = TaskService(db)

    # Get existing extraction
    task = await task_service.get_existing_extraction(
        file_id=file_id,
        user_uuid=current_user.uuid,
    )

    if not task:
        raise APIException(
            error_code="EXTRACTION_NOT_FOUND",
            message="该文件尚未进行文本提取",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return {
        "success": True,
        "data": {
            "task_id": task.task_id,
            "file_id": file_id,
            "status": task.status,
            "result": task.result,
            "completed_at": task.completed_at,
        },
    }


@router.post(
    "/{file_id}/summarize",
    response_model=Dict[str, Any],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Summarize document",
    description="Generate a summary of the document",
)
async def summarize_document(
    file_id: str,
    request: Optional[SummarizeRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a summary of a document."""
    task_service = TaskService(db)
    file_service = FileService(db)

    file = await file_service.get_file(file_id, current_user.uuid)
    if not file:
        raise APIException(
            error_code="FILE_NOT_FOUND",
            message=f"文件不存在: {file_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if not file.extracted_text:
        raise APIException(
            error_code="EXTRACTION_REQUIRED",
            message="请先进行文本提取",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    options = request.model_dump() if request else {}
    options["api_key"] = current_user.api_key

    task = await task_service.create_task(
        user_uuid=current_user.uuid,
        file_id=file_id,
        task_type="summarize",
        options=options,
    )

    try:
        job = task_queue.enqueue(
            summarize_document_task,
            task_id=task.task_id,
            file_id=file_id,
            user_uuid=current_user.uuid,
            text=file.extracted_text,
            options=options,
        )
        await task_service.update_task_status(task_id=task.task_id, job_id=job.id)
        logger.info(f"Enqueued summarize task {task.task_id} as job {job.id}")
    except Exception as e:
        logger.warning(f"RQ not available, running directly: {e}")
        try:
            result = summarize_document_task(
                task_id=task.task_id,
                file_id=file_id,
                user_uuid=current_user.uuid,
                text=file.extracted_text,
                options=options,
            )
            await task_service.update_task_status(
                task_id=task.task_id,
                status="completed",
                progress=100,
                result=result,
            )
        except Exception as ex:
            await task_service.update_task_status(
                task_id=task.task_id,
                status="failed",
                error_message=str(ex),
            )

    return {
        "success": True,
        "data": {
            "task_id": task.task_id,
            "file_id": file_id,
            "task_type": "summarize",
            "status": task.status,
        },
        "message": "文档摘要任务已创建",
    }


@router.post(
    "/{file_id}/qa",
    response_model=Dict[str, Any],
    summary="Ask question about document",
    description="Ask a question about the document content",
)
async def question_answer(
    file_id: str,
    request: QARequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Answer a question about document content."""
    file_service = FileService(db)

    file = await file_service.get_file(file_id, current_user.uuid)
    if not file:
        raise APIException(
            error_code="FILE_NOT_FOUND",
            message=f"文件不存在: {file_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if not file.extracted_text:
        raise APIException(
            error_code="EXTRACTION_REQUIRED",
            message="请先进行文本提取",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    api_key = current_user.api_key
    if not api_key:
        from core.config import settings

        api_key = settings.dashscope_api_key

    if not api_key:
        raise APIException(
            error_code="API_KEY_REQUIRED",
            message="请先配置API Key",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        from services.llm_service import LLMService

        llm = LLMService(api_key=api_key)

        result = llm.answer_question(
            text=file.extracted_text,
            question=request.question,
            history=request.history,
        )

        return {
            "success": True,
            "data": {
                "answer": result.get("answer", ""),
                "confidence": result.get("confidence", 0.5),
                "sources": result.get("sources", []) if request.include_sources else [],
                "suggested_questions": result.get("suggested_questions", [])
                if request.include_suggestions
                else [],
            },
        }
    except Exception as e:
        logger.error(f"Q&A failed for file {file_id}: {e}")
        raise APIException(
            error_code="QA_FAILED",
            message=f"问答失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/{file_id}/rewrite",
    response_model=Dict[str, Any],
    summary="Rewrite text",
    description="Rewrite text from the document in a different style",
)
async def rewrite_text(
    file_id: str,
    request: RewriteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rewrite text in a different style."""
    file_service = FileService(db)

    file = await file_service.get_file(file_id, current_user.uuid)
    if not file:
        raise APIException(
            error_code="FILE_NOT_FOUND",
            message=f"文件不存在: {file_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    api_key = current_user.api_key
    if not api_key:
        from core.config import settings

        api_key = settings.dashscope_api_key

    if not api_key:
        raise APIException(
            error_code="API_KEY_REQUIRED",
            message="请先配置API Key",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        from services.llm_service import LLMService

        llm = LLMService(api_key=api_key)

        result = llm.rewrite_text(
            text=request.text,
            rewrite_type=request.rewrite_type.value,
            tone=request.tone,
            length=request.length.value,
            language=request.language,
        )

        return {
            "success": True,
            "data": {
                "rewritten_text": result.get("rewritten_text", ""),
                "original_length": len(request.text),
                "rewritten_length": len(result.get("rewritten_text", "")),
                "improvements": result.get("improvements", []),
                "alternatives": [],
            },
        }
    except Exception as e:
        logger.error(f"Rewrite failed: {e}")
        raise APIException(
            error_code="REWRITE_FAILED",
            message=f"改写失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/{file_id}/mindmap",
    response_model=Dict[str, Any],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate mindmap",
    description="Generate a hierarchical mindmap from the document",
)
async def generate_mindmap(
    file_id: str,
    request: Optional[MindmapRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a mindmap from document content."""
    task_service = TaskService(db)
    file_service = FileService(db)

    file = await file_service.get_file(file_id, current_user.uuid)
    if not file:
        raise APIException(
            error_code="FILE_NOT_FOUND",
            message=f"文件不存在: {file_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if not file.extracted_text:
        raise APIException(
            error_code="EXTRACTION_REQUIRED",
            message="请先进行文本提取",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    api_key = current_user.api_key
    if not api_key:
        from core.config import settings

        api_key = settings.dashscope_api_key

    if not api_key:
        raise APIException(
            error_code="API_KEY_REQUIRED",
            message="请先配置API Key",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    options = (
        request.model_dump() if request else {"max_depth": 3, "include_keywords": True}
    )

    task = await task_service.create_task(
        user_uuid=current_user.uuid,
        file_id=file_id,
        task_type="mindmap",
        options=options,
    )

    try:
        from services.llm_service import LLMService

        llm = LLMService(api_key=api_key)

        result = llm.generate_mindmap(
            text=file.extracted_text,
            max_depth=options.get("max_depth", 3),
            include_keywords=options.get("include_keywords", True),
        )

        await task_service.update_task_status(
            task_id=task.task_id,
            status="completed",
            progress=100,
            result=result,
        )

        return {
            "success": True,
            "data": {
                "task_id": task.task_id,
                "file_id": file_id,
                "task_type": "mindmap",
                "status": "completed",
                "result": result,
            },
            "message": "思维导图生成完成",
        }
    except Exception as e:
        logger.error(f"Mindmap generation failed for file {file_id}: {e}")
        await task_service.update_task_status(
            task_id=task.task_id,
            status="failed",
            error_message=str(e),
        )
        raise APIException(
            error_code="MINDMAP_FAILED",
            message=f"思维导图生成失败: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
