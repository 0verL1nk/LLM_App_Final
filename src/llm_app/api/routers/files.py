"""
File management router endpoints
"""
import os
from typing import Optional
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends,
    HTTPException,
    Query,
    Response,
    Form,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from llm_app.api.deps import get_db, get_current_user
from llm_app.schemas.file import (
    UploadResponse,
    UploadData,
    FileListResponse,
    FileListData,
    FileDetailsResponse,
    MessageResponse,
    PaginationInfo,
)
from llm_app.services.file_service import FileService
from llm_app.models.user import User
from llm_app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/files",
    tags=["files"],
)

# Define types
CurrentUser = User


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=201,
    summary="Upload file",
    description="Upload a document for processing (PDF, DOCX, or TXT, max 50MB)"
)
async def upload_file(
    response: Response,
    file: UploadFile = File(..., description="File to upload"),
    tags: Optional[list[str]] = Form(
        None,
        description="Optional tags (max 10)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Upload a file with optional tags

    Args:
        file: File to upload (PDF, DOCX, or TXT)
        tags: Optional comma-separated tags
        db: Database session
        current_user: Current authenticated user

    Returns:
        UploadResponse with file metadata

    Raises:
        HTTPException: If file validation fails or upload error occurs
    """
    try:
        # Validate tags
        if tags and len(tags) > 10:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "VALIDATION_ERROR",
                    "message": "最多只能添加10个标签",
                    "details": {"tag_count": len(tags), "max_tags": 10},
                },
            )

        # Save file
        file_record, is_duplicate = await FileService.save_uploaded_file(
            db=db,
            file=file,
            user_uuid=str(current_user.uuid),
            tags=tags,
        )

        # Generate download URL
        download_url = f"/api/v1/files/{file_record.id}/download"

        response.status_code = 200 if is_duplicate else 201

        upload_data = UploadData(
            file_id=str(file_record.id),
            original_filename=file_record.original_filename,
            filename=file_record.filename,
            file_size=file_record.file_size,
            mime_type=file_record.mime_type,
            md5=file_record.md5,
            upload_url=download_url,
            processing_status=file_record.processing_status,
            created_at=file_record.created_at,
        )

        message = "文件已存在" if is_duplicate else "文件上传成功"

        return UploadResponse(
            data=upload_data,
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "UPLOAD_FAILED",
                "message": "文件上传失败",
                "details": {"error": str(e)}
            }
        )


@router.get(
    "",
    response_model=FileListResponse,
    summary="List files",
    description="Get paginated list of user's files"
)
async def list_files(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search keyword for filename"),
    status: Optional[str] = Query(
        None,
        description="Filter by processing status (all, pending, processing, completed, failed)"
    ),
    sort: str = Query(
        "created_desc",
        description="Sort order (created_desc, created_asc, name_asc, name_desc)"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    List user's files with pagination and filtering

    Args:
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        search: Search keyword for filename
        status: Filter by processing status
        sort: Sort order
        db: Database session
        current_user: Current authenticated user

    Returns:
        FileListResponse with paginated file list
    """
    try:
        # Validate status filter
        if status and status not in ["all", "pending", "processing", "completed", "failed"]:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "VALIDATION_ERROR",
                    "message": "无效的状态过滤条件",
                    "details": {
                        "status": status,
                        "allowed_values": ["all", "pending", "processing", "completed", "failed"]
                    }
                }
            )

        # Validate sort order
        if sort not in ["created_desc", "created_asc", "name_asc", "name_desc"]:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "VALIDATION_ERROR",
                    "message": "无效的排序方式",
                    "details": {
                        "sort": sort,
                        "allowed_values": ["created_desc", "created_asc", "name_asc", "name_desc"]
                    }
                }
            )

        # Get files
        files, total = await FileService.list_files(
            db=db,
            user_uuid=str(current_user.uuid),
            page=page,
            page_size=page_size,
            search=search,
            status=status,
            sort=sort
        )

        # Calculate pagination
        total_pages = (total + page_size - 1) // page_size

        pagination = PaginationInfo(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages
        )

        return FileListResponse(
            data=FileListData(items=files, pagination=pagination),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File list failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "LIST_FAILED",
                "message": "获取文件列表失败",
                "details": {"error": str(e)}
            }
        )


@router.get(
    "/{file_id}",
    response_model=FileDetailsResponse,
    summary="Get file details",
    description="Get detailed information about a specific file"
)
async def get_file_details(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Get detailed file information

    Args:
        file_id: File identifier
        db: Database session
        current_user: Current authenticated user

    Returns:
        FileDetailsResponse with file details

    Raises:
        HTTPException: If file not found
    """
    try:
        file = await FileService.get_file_by_id(
            db=db,
            file_id=file_id,
            user_uuid=str(current_user.uuid)
        )

        return FileDetailsResponse(data=file)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get file details failed for {file_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GET_DETAILS_FAILED",
                "message": "获取文件详情失败",
                "details": {"error": str(e)}
            }
        )


@router.delete(
    "/{file_id}",
    response_model=MessageResponse,
    summary="Delete file",
    description="Delete a file and all associated content"
)
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Delete a file

    Args:
        file_id: File identifier
        db: Database session
        current_user: Current authenticated user

    Returns:
        MessageResponse with success message

    Raises:
        HTTPException: If file not found or deletion fails
    """
    try:
        success = await FileService.delete_file(
            db=db,
            file_id=file_id,
            user_uuid=str(current_user.uuid)
        )

        if not success:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "FILE_NOT_FOUND",
                    "message": "文件不存在",
                    "details": {"file_id": file_id}
                }
            )

        return MessageResponse(message="文件删除成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete file failed for {file_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "DELETE_FAILED",
                "message": "文件删除失败",
                "details": {"error": str(e)}
            }
        )


@router.get(
    "/{file_id}/download",
    summary="Download file",
    description="Download the original uploaded file"
)
async def download_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Download a file

    Args:
        file_id: File identifier
        db: Database session
        current_user: Current authenticated user

    Returns:
        File stream

    Raises:
        HTTPException: If file not found
    """
    try:
        file = await FileService.get_file_for_download(
            db=db,
            file_id=file_id,
            user_uuid=str(current_user.uuid)
        )

        # Check if file exists on disk
        if not os.path.exists(file.file_path):
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "FILE_NOT_FOUND",
                    "message": "文件不存在",
                    "details": {"file_id": file_id}
                }
            )

        # Determine content type
        content_type = file.mime_type or "application/octet-stream"

        # Return file stream
        def file_generator():
            with open(file.file_path, "rb") as file_handle:
                yield from file_handle

        return StreamingResponse(
            file_generator(),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file.original_filename}"',
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download file failed for {file_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "DOWNLOAD_FAILED",
                "message": "文件下载失败",
                "details": {"error": str(e)}
            }
        )
