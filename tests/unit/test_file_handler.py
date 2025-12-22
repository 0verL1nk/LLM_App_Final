"""
Unit tests for FileHandler.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, MagicMock, patch

from src.llm_app.core.file_handler import FileHandler
from src.llm_app.core.database import DatabaseManager


class TestFileHandler:
    """Test cases for FileHandler."""

    def test_init(self, temp_db):
        """Test initialization."""
        db = DatabaseManager(db_path=temp_db)
        handler = FileHandler(db_manager=db)
        assert handler.db == db

    def test_calculate_md5(self):
        """Test MD5 calculation."""
        handler = FileHandler()

        # Create a mock file
        mock_file = MagicMock()
        mock_file.read.side_effect = [b'test content', b'']

        md5 = handler.calculate_md5(mock_file)
        assert len(md5) == 32  # MD5 hash length

    def test_calculate_md5_empty_file(self):
        """Test MD5 calculation for empty file."""
        handler = FileHandler()

        mock_file = MagicMock()
        mock_file.read.side_effect = [b'', b'']

        md5 = handler.calculate_md5(mock_file)
        assert md5 == 'd41d8cd98f00b204e9800998ecf8427e'  # MD5 of empty string

    def test_get_file_uid_existing(self, temp_db, sample_file_data):
        """Test getting existing file UID."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        handler = FileHandler(db_manager=db)

        # Save file first
        db.save_file_to_database(**sample_file_data)

        # Get UID by MD5
        uid = handler.get_file_uid(sample_file_data['md5'])
        assert uid == sample_file_data['uid']

    def test_get_file_uid_new(self, temp_db):
        """Test generating new file UID."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        handler = FileHandler(db_manager=db)

        # Get UID for non-existent MD5
        md5 = 'nonexistent_md5_hash'
        uid = handler.get_file_uid(md5)

        # Should generate a new UUID
        assert len(uid) == 36
        assert uid.count('-') == 4  # UUID format

    def test_save_uploaded_file(self, temp_db, sample_file_data):
        """Test saving uploaded file."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        handler = FileHandler(db_manager=db)

        # Create mock file
        mock_file = MagicMock()
        mock_file.name = sample_file_data['original_filename']
        mock_file.read.side_effect = [b'file content', b'']

        # Create temp directory for upload
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save file
            result = handler.save_uploaded_file(
                mock_file,
                sample_file_data['uuid'],
                tmpdir
            )

            assert 'file_path' in result
            assert 'file_name' in result
            assert 'uid' in result
            assert 'created_at' in result
            assert result['file_name'] == 'test_paper'

            # Verify file exists
            assert os.path.exists(result['file_path'])

    def test_save_uploaded_file_duplicate(self, temp_db, sample_file_data):
        """Test saving duplicate file."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        handler = FileHandler(db_manager=db)

        # Create mock file
        mock_file = MagicMock()
        mock_file.name = sample_file_data['original_filename']
        mock_file.read.side_effect = [b'file content', b'', b'file content', b'']

        with tempfile.TemporaryDirectory() as tmpdir:
            # Save file first time
            result1 = handler.save_uploaded_file(
                mock_file,
                sample_file_data['uuid'],
                tmpdir
            )

            # Reset file pointer for second read
            mock_file.seek(0)

            # Save same file again
            result2 = handler.save_uploaded_file(
                mock_file,
                sample_file_data['uuid'],
                tmpdir
            )

            # Should get same UID
            assert result1['uid'] == result2['uid']

    @patch('textract.process')
    def test_extract_text_pdf(self, mock_textract):
        """Test extracting text from PDF."""
        mock_textract.return_value = b'PDF content here'

        handler = FileHandler()
        result = handler.extract_text('test.pdf')

        assert result['result'] == 1
        assert 'PDF content here' in result['text']

    @patch('textract.process')
    def test_extract_text_docx(self, mock_textract):
        """Test extracting text from DOCX."""
        mock_textract.return_value = b'DOCX content here'

        handler = FileHandler()
        result = handler.extract_text('test.docx')

        assert result['result'] == 1
        assert 'DOCX content here' in result['text']

    @patch('textract.process')
    def test_extract_text_txt(self, mock_textract):
        """Test extracting text from TXT."""
        mock_textract.return_value = b'Text content here'

        handler = FileHandler()
        result = handler.extract_text('test.txt')

        assert result['result'] == 1
        assert 'Text content here' in result['text']

    @patch('textract.process')
    def test_extract_text_unsupported_format(self, mock_textract):
        """Test extracting text from unsupported format."""
        handler = FileHandler()
        result = handler.extract_text('test.xyz')

        assert result['result'] == -1
        assert '不支持的文件类型' in result['text']

    @patch('textract.process')
    def test_extract_text_error_handling(self, mock_textract):
        """Test error handling in text extraction."""
        mock_textract.side_effect = Exception('Extraction failed')

        handler = FileHandler()
        result = handler.extract_text('test.pdf')

        assert result['result'] == -1

    def test_extract_text_braces_escaping(self):
        """Test that braces are escaped in extracted text."""
        with patch('textract.process') as mock_textract:
            mock_textract.return_value = b'Text with {braces}'

            handler = FileHandler()
            result = handler.extract_text('test.txt')

            assert result['result'] == 1
            assert '{{' in result['text']  # Escaped opening brace
            assert '}}' in result['text']  # Escaped closing brace

    def test_process_uploaded_file_success(self, temp_db, sample_file_data):
        """Test successful file processing."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        handler = FileHandler(db_manager=db)

        # Create mock file
        mock_file = MagicMock()
        mock_file.name = sample_file_data['original_filename']
        mock_file.read.side_effect = [b'file content', b'']

        with tempfile.TemporaryDirectory() as tmpdir:
            # Process file
            success, message, file_info = handler.process_uploaded_file(
                mock_file,
                sample_file_data['uuid']
            )

            assert success is True
            assert '成功' in message
            assert 'file_path' in file_info

    def test_process_uploaded_file_failure(self, temp_db):
        """Test file processing failure."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        handler = FileHandler(db_manager=db)

        # Create mock file that raises error
        mock_file = MagicMock()
        mock_file.read.side_effect = Exception('Read error')

        # Process file
        success, message, file_info = handler.process_uploaded_file(
            mock_file,
            'uuid'
        )

        assert success is False
        assert '失败' in message
        assert file_info == {}

    def test_get_user_files(self, temp_db, sample_file_data):
        """Test getting user files."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        handler = FileHandler(db_manager=db)

        # Save file
        db.save_file_to_database(**sample_file_data)

        # Get files
        files = handler.get_user_files(sample_file_data['uuid'])
        assert len(files) == 1
        assert files[0][1] == sample_file_data['original_filename']

    def test_get_user_files_empty(self, temp_db):
        """Test getting files for user with no files."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        handler = FileHandler(db_manager=db)

        # Get files for user with no files
        files = handler.get_user_files('nonexistent-uuid')
        assert files == []

    def test_md5_uniqueness(self):
        """Test that different files have different MD5s."""
        handler = FileHandler()

        # Create mock files with different content
        mock_file1 = MagicMock()
        mock_file1.read.side_effect = [b'content1', b'']

        mock_file2 = MagicMock()
        mock_file2.read.side_effect = [b'content2', b'']

        md5_1 = handler.calculate_md5(mock_file1)
        md5_2 = handler.calculate_md5(mock_file2)

        assert md5_1 != md5_2

    def test_file_path_handling(self, temp_db, sample_file_data):
        """Test proper file path handling."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        handler = FileHandler(db_manager=db)

        # Create mock file with extension
        mock_file = MagicMock()
        mock_file.name = 'document.pdf'
        mock_file.read.side_effect = [b'content', b'']

        with tempfile.TemporaryDirectory() as tmpdir:
            result = handler.save_uploaded_file(
                mock_file,
                sample_file_data['uuid'],
                tmpdir
            )

            # Verify file is saved with correct extension
            assert result['file_path'].endswith('.pdf')

    def test_file_content_preservation(self, temp_db, sample_file_data):
        """Test that file content is preserved."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        handler = FileHandler(db_manager=db)

        # Create mock file with specific content
        content = b'Important document content 12345'
        mock_file = MagicMock()
        mock_file.name = sample_file_data['original_filename']
        mock_file.read.side_effect = [content, b'']

        with tempfile.TemporaryDirectory() as tmpdir:
            result = handler.save_uploaded_file(
                mock_file,
                sample_file_data['uuid'],
                tmpdir
            )

            # Verify file content
            with open(result['file_path'], 'rb') as f:
                saved_content = f.read()

            assert saved_content == content