"""
File service for upload, storage, and management
"""
import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, delete
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import selectinload

from models.file import File
from core.logger import get_logger

logger = get_logger(__name__)

# File storage configuration
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Supported file types
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain"
}

# File size limit (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


class FileService:
    """Service class for file operations"""

    @staticmethod
    async def check_md5_exists(
        db: AsyncSession,
        md5_hash: str,
        user_uuid: Optional[str] = None,
    ) -> Optional[File]:
        """
        Check if a file with the given MD5 already exists

        Args:
            db: Database session
            md5_hash: MD5 hash to check

        Returns:
            File instance if found, None otherwise
        """
        try:
            query = select(File).where(File.md5 == md5_hash)
            if user_uuid:
                query = query.where(File.user_uuid == user_uuid)
            result = await db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to check MD5 {md5_hash}: {str(e)}")
            raise

    @staticmethod
    async def save_uploaded_file(
        db: AsyncSession,
        file: UploadFile,
        user_uuid: str,
        tags: Optional[List[str]] = None
    ) -> Tuple[File, bool]:
        """
        Save an uploaded file with validation and deduplication

        Args:
            db: Database session
            file: UploadFile object from FastAPI
            user_uuid: UUID of the user uploading the file
            tags: Optional list of tags

        Returns:
            Tuple of (File instance, is_duplicate)

        Raises:
            HTTPException: If file is invalid, too large, or duplicate
        """
        try:
            # Read file content to memory for validation and MD5 calculation
            content = await file.read()
            file_size = len(content)

            # Validate file size
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "FILE_TOO_LARGE",
                        "message": f"文件大小超过限制 (最大 {MAX_FILE_SIZE // (1024*1024)}MB)",
                        "details": {"file_size": file_size, "max_size": MAX_FILE_SIZE}
                    }
                )

            # Validate file type
            file_extension = Path(file.filename).suffix.lower()
            if file_extension not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "FILE_TYPE_INVALID",
                        "message": f"不支持的文件类型: {file_extension}",
                        "details": {
                            "file_extension": file_extension,
                            "allowed_extensions": list(ALLOWED_EXTENSIONS)
                        }
                    }
                )

            # Validate MIME type
            if file.content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "FILE_TYPE_INVALID",
                        "message": f"不支持的MIME类型: {file.content_type}",
                        "details": {
                            "mime_type": file.content_type,
                            "allowed_mime_types": list(ALLOWED_MIME_TYPES)
                        }
                    }
                )

            # Calculate MD5 hash
            md5_hash = hashlib.md5(content).hexdigest()

            # Check for duplicate
            existing_file = await FileService.check_md5_exists(db, md5_hash, user_uuid)
            if existing_file:
                logger.info(
                    "Duplicate file upload detected for user %s: %s",
                    user_uuid,
                    existing_file.id,
                )
                return existing_file, True

            # Generate unique filename
            file_uuid = str(uuid.uuid4())
            storage_filename = f"{file_uuid}{file_extension}"
            file_path = UPLOAD_DIR / storage_filename

            # Save file to disk
            with open(file_path, "wb") as f:
                f.write(content)

            # Create database record
            file_record = File(
                id=file_uuid,
                original_filename=file.filename,
                filename=storage_filename,
                file_path=str(file_path),
                file_ext=file_extension,
                file_size=file_size,
                md5=md5_hash,
                mime_type=file.content_type or "application/octet-stream",
                user_uuid=user_uuid,
                processing_status="pending",
                tags=tags or [],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            db.add(file_record)
            await db.commit()
            await db.refresh(file_record)

            logger.info(f"File saved successfully: {file.filename} ({file_uuid})")
            return file_record, False

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to save file {file.filename}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "FILE_SAVE_ERROR",
                    "message": "文件保存失败",
                    "details": {"error": str(e)}
                }
            )

    @staticmethod
    async def list_files(
        db: AsyncSession,
        user_uuid: str,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        sort: str = "created_desc"
    ) -> Tuple[List[File], int]:
        """
        List user's files with pagination and filtering

        Args:
            db: Database session
            user_uuid: UUID of the user
            page: Page number (1-indexed)
            page_size: Number of items per page
            search: Search keyword for filename
            status: Filter by processing status
            sort: Sort order (created_desc, created_asc, name_asc, name_desc)

        Returns:
            Tuple of (file_list, total_count)
        """
        try:
            # Build query
            query = select(File).where(File.user_uuid == user_uuid)

            # Apply filters
            if search:
                query = query.where(
                    File.original_filename.ilike(f"%{search}%")
                )

            if status and status != "all":
                query = query.where(File.processing_status == status)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total = total_result.scalar()

            # Apply sorting
            if sort == "created_desc":
                query = query.order_by(File.created_at.desc())
            elif sort == "created_asc":
                query = query.order_by(File.created_at.asc())
            elif sort == "name_asc":
                query = query.order_by(File.original_filename.asc())
            elif sort == "name_desc":
                query = query.order_by(File.original_filename.desc())

            # Apply pagination
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)

            # Execute query
            result = await db.execute(query)
            files = result.scalars().all()

            logger.info(f"Listed {len(files)} files for user {user_uuid} (page {page})")
            return files, total

        except Exception as e:
            logger.error(f"Failed to list files for user {user_uuid}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "FILE_LIST_ERROR",
                    "message": "获取文件列表失败",
                    "details": {"error": str(e)}
                }
            )

    @staticmethod
    async def get_file_by_id(
        db: AsyncSession,
        file_id: str,
        user_uuid: str
    ) -> File:
        """
        Get file by ID (user must be owner)

        Args:
            db: Database session
            file_id: File ID
            user_uuid: UUID of the requesting user

        Returns:
            File instance

        Raises:
            HTTPException: If file not found or access denied
        """
        try:
            result = await db.execute(
                select(File).where(
                    and_(
                        File.id == file_id,
                        File.user_uuid == user_uuid
                    )
                )
            )
            file = result.scalar_one_or_none()

            if not file:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "FILE_NOT_FOUND",
                        "message": "文件不存在",
                        "details": {"file_id": file_id}
                    }
                )

            return file

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get file {file_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "FILE_GET_ERROR",
                    "message": "获取文件信息失败",
                    "details": {"error": str(e)}
                }
            )

    @staticmethod
    async def delete_file(
        db: AsyncSession,
        file_id: str,
        user_uuid: str
    ) -> bool:
        """
        Delete a file and its database record

        Args:
            db: Database session
            file_id: File ID to delete
            user_uuid: UUID of the requesting user (must be owner)

        Returns:
            True if deleted, False if not found

        Raises:
            HTTPException: If deletion fails
        """
        try:
            # Get file
            file = await FileService.get_file_by_id(db, file_id, user_uuid)

            # Delete physical file
            try:
                if os.path.exists(file.file_path):
                    os.remove(file.file_path)
                    logger.info(f"Deleted physical file: {file.file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete physical file {file.file_path}: {str(e)}")

            # Delete database record without loading relationships
            await db.execute(
                delete(File).where(
                    and_(
                        File.id == file_id,
                        File.user_uuid == user_uuid,
                    )
                )
            )
            await db.commit()

            logger.info(f"File deleted successfully: {file_id}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to delete file {file_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "FILE_DELETE_ERROR",
                    "message": "文件删除失败",
                    "details": {"error": str(e)}
                }
            )

    @staticmethod
    async def get_file_for_download(
        db: AsyncSession,
        file_id: str,
        user_uuid: str
    ) -> File:
        """
        Get file for download (with access control)

        Args:
            db: Database session
            file_id: File ID
            user_uuid: UUID of the requesting user

        Returns:
            File instance

        Raises:
            HTTPException: If file not found or access denied
        """
        try:
            file = await FileService.get_file_by_id(db, file_id, user_uuid)

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

            return file

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get file for download {file_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "FILE_DOWNLOAD_ERROR",
                    "message": "文件下载准备失败",
                    "details": {"error": str(e)}
                }
            )

    @staticmethod
    async def update_processing_status(
        db: AsyncSession,
        file_id: str,
        status: str
    ) -> bool:
        """
        Update file processing status

        Args:
            db: Database session
            file_id: File ID
            status: New processing status

        Returns:
            True if updated

        Raises:
            HTTPException: If update fails
        """
        try:
            result = await db.execute(
                select(File).where(File.id == file_id)
            )
            file = result.scalar_one_or_none()

            if not file:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "FILE_NOT_FOUND",
                        "message": "文件不存在",
                        "details": {"file_id": file_id}
                    }
                )

            file.processing_status = status
            file.updated_at = datetime.utcnow()
            await db.commit()

            logger.info(f"Updated processing status for file {file_id}: {status}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update processing status for {file_id}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "STATUS_UPDATE_ERROR",
                    "message": "状态更新失败",
                    "details": {"error": str(e)}
                }
            )

    def __init__(self, db: AsyncSession):
        """Initialize FileService with database session"""
        self.db = db

    async def get_file(self, file_id: str, user_uuid: str) -> Optional[File]:
        """
        Get file by ID for a specific user.

        Args:
            file_id: File ID
            user_uuid: User's UUID

        Returns:
            File object or None if not found
        """
        result = await self.db.execute(
            select(File).where(
                and_(File.id == file_id, File.user_uuid == user_uuid)
            )
        )
        return result.scalar_one_or_none()

    async def update_file_content(
        self,
        file_id: str,
        user_uuid: str,
        extracted_text: Optional[str] = None,
        word_count: Optional[int] = None,
    ) -> bool:
        """
        Update file with extracted content.

        Args:
            file_id: File ID
            user_uuid: User's UUID
            extracted_text: Extracted text content
            word_count: Word count

        Returns:
            True if updated successfully
        """
        file = await self.get_file(file_id, user_uuid)
        if not file:
            return False

        if extracted_text is not None:
            file.extracted_text = extracted_text
        if word_count is not None:
            file.word_count = word_count

        file.processing_status = "completed"
        file.updated_at = datetime.utcnow()

        await self.db.commit()
        logger.info(f"Updated file content for {file_id}")
        return True
