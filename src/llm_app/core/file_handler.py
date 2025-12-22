"""
File handling module for the LLM App.

This module provides file upload, processing, and storage functionality
including MD5 calculation, deduplication, and text extraction.
"""

import datetime
import hashlib
import os
from typing import Dict, Optional, Tuple

import textract

from .database import DatabaseManager
from ..config import Config


class FileHandler:
    """File handling and processing manager."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        """Initialize file handler.

        Args:
            db_manager: Database manager instance. Creates new one if None.
        """
        self.db = db_manager or DatabaseManager()
        Config.ensure_directories()

    @staticmethod
    def calculate_md5(file) -> str:
        """Calculate MD5 hash of uploaded file.

        Args:
            file: Streamlit uploaded file object

        Returns:
            MD5 hash string
        """
        md5_hash = hashlib.md5()
        # Read file in chunks to handle large files
        for chunk in iter(lambda: file.read(4096), b""):
            md5_hash.update(chunk)
        return md5_hash.hexdigest()

    def get_file_uid(self, md5_value: str) -> str:
        """Get file UID for given MD5.

        Args:
            md5_value: File MD5 hash

        Returns:
            File UID (existing or new)
        """
        existing_uid = self.db.get_uid_by_md5(md5_value)
        if existing_uid:
            return existing_uid

        # Generate new UID for new file
        from .auth import AuthManager

        return AuthManager().generate_uuid()

    def save_uploaded_file(
        self, uploaded_file, uuid_value: str, save_dir: str
    ) -> Dict[str, str]:
        """Save uploaded file to storage and database.

        Args:
            uploaded_file: Streamlit uploaded file object
            uuid_value: User UUID
            save_dir: Directory to save files

        Returns:
            Dictionary with file information
        """
        # Calculate MD5 for deduplication
        uploaded_file.seek(0)  # Reset file pointer
        md5_value = self.calculate_md5(uploaded_file)

        # Get or generate file UID
        uid = self.get_file_uid(md5_value)

        # Get file info
        original_filename = uploaded_file.name
        file_extension = os.path.splitext(original_filename)[-1]
        file_name = os.path.splitext(original_filename)[0]

        # Save file
        saved_filename = f"{uid}{file_extension}"
        file_path = os.path.join(save_dir, saved_filename)

        # Only save if not already exists
        if not os.path.exists(file_path):
            uploaded_file.seek(0)  # Reset file pointer again
            with open(file_path, "wb") as f:
                f.write(uploaded_file.read())

        # Save to database
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db.save_file_to_database(
            original_filename=original_filename,
            uid=uid,
            uuid_value=uuid_value,
            md5_value=md5_value,
            file_path=file_path,
            created_at=current_time,
        )

        return {
            "file_path": file_path,
            "file_name": file_name,
            "uid": uid,
            "created_at": current_time,
            "md5": md5_value,
        }

    @staticmethod
    def extract_text(file_path: str) -> Dict[str, str]:
        """Extract text from file.

        Args:
            file_path: Path to file

        Returns:
            Dictionary with result and text
            - result: 1 for success, -1 for failure
            - text: Extracted text or error message
        """
        file_type = file_path.split(".")[-1].lower()

        if file_type in ["doc", "docx", "pdf", "txt"]:
            try:
                extracted_text = textract.process(file_path).decode("utf-8")
                # Replace { and } to prevent parsing as variables
                safe_text = extracted_text.replace("{", "{{").replace("}", "}}")
                return {"result": 1, "text": safe_text}
            except Exception as e:
                return {"result": -1, "text": str(e)}
        else:
            return {"result": -1, "text": "不支持的文件类型!"}

    def process_uploaded_file(
        self, uploaded_file, uuid_value: str
    ) -> Tuple[bool, str, Dict[str, str]]:
        """Process uploaded file (save and extract text).

        Args:
            uploaded_file: Streamlit uploaded file object
            uuid_value: User UUID

        Returns:
            Tuple of (success, message, file_info_dict)
        """
        try:
            file_info = self.save_uploaded_file(
                uploaded_file, uuid_value, Config.get_uploads_dir()
            )
            return True, "文档上传成功", file_info
        except Exception as e:
            return False, f"文档上传失败: {e!s}", {}

    def get_user_files(self, uuid_value: str) -> list:
        """Get all files for a user.

        Args:
            uuid_value: User UUID

        Returns:
            List of user files
        """
        return self.db.get_user_files(uuid_value)
