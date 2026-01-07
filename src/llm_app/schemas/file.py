"""
Pydantic schemas for file operations
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FileMetadata(BaseModel):
    """File metadata for listing and responses"""
    model_config = ConfigDict(from_attributes=True)

    file_id: str = Field(..., description="Unique file identifier")
    original_filename: str = Field(..., description="Original filename provided by user")
    filename: str = Field(..., description="Storage filename")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the file")
    processing_status: str = Field(
        ...,
        description="Current processing status",
        examples=["pending", "processing", "completed", "failed"],
    )
    is_favorite: bool = Field(default=False, description="User's favorite status")
    tags: Optional[List[str]] = Field(None, description="Optional file tags")
    created_at: datetime = Field(..., description="File upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class FileDetails(FileMetadata):
    """Detailed file information including extracted content"""
    extracted_text: Optional[str] = Field(None, description="Extracted text content")
    word_count: Optional[int] = Field(None, description="Word count of extracted text")
    md5: str = Field(..., description="MD5 hash for deduplication")


class FileUpload(BaseModel):
    """File upload request model"""
    tags: Optional[List[str]] = Field(
        None,
        max_items=10,
        description="Optional file tags (max 10)",
    )


class PaginationInfo(BaseModel):
    """Pagination metadata"""
    page: int = Field(..., description="Current page number", examples=[1])
    page_size: int = Field(..., description="Number of items per page", examples=[20])
    total: int = Field(..., description="Total number of items", examples=[50])
    total_pages: int = Field(..., description="Total number of pages", examples=[3])


class FileListData(BaseModel):
    """File list payload"""
    items: List[FileMetadata] = Field(..., description="List of file metadata")
    pagination: PaginationInfo = Field(..., description="Pagination information")


class FileListResponse(BaseModel):
    """Paginated file list response"""
    success: bool = Field(default=True, description="Operation success status")
    data: FileListData = Field(..., description="Response data containing items and pagination info")


class UploadData(BaseModel):
    """File upload payload"""
    model_config = ConfigDict(from_attributes=True)

    file_id: str = Field(..., description="Unique file identifier")
    original_filename: str = Field(..., description="Original filename provided by user")
    filename: str = Field(..., description="Storage filename")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the file")
    md5: str = Field(..., description="MD5 hash for deduplication")
    upload_url: str = Field(..., description="Download URL for the file")
    processing_status: str = Field(
        ...,
        description="Current processing status",
        examples=["pending", "processing", "completed", "failed"],
    )
    created_at: datetime = Field(..., description="File upload timestamp")


class UploadResponse(BaseModel):
    """File upload response"""
    success: bool = Field(default=True, description="Operation success status")
    data: UploadData = Field(..., description="Uploaded file metadata")
    message: str = Field(default="文件上传成功", description="Response message")


class FileDetailsResponse(BaseModel):
    """Detailed file information response"""
    success: bool = Field(default=True, description="Operation success status")
    data: FileDetails = Field(..., description="Detailed file information")


class MessageResponse(BaseModel):
    """Generic message response"""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(..., description="Response message")


class FavoriteToggleResponse(BaseModel):
    """Response for favorite toggle operation"""
    success: bool = Field(default=True, description="Operation success status")
    data: FileMetadata = Field(..., description="Updated file metadata")
    message: str = Field(default="收藏状态已更新", description="Response message")


class FavoriteListResponse(BaseModel):
    """Paginated favorites list response"""
    success: bool = Field(default=True, description="Operation success status")
    data: FileListData = Field(..., description="Response data containing items and pagination info")
