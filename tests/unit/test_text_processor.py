"""
Unit tests for TextProcessor.
"""

import pytest
import tempfile
from unittest.mock import MagicMock, patch

from src.llm_app.core.text_processor import TextProcessor
from src.llm_app.core.database import DatabaseManager
from src.llm_app.core.file_handler import FileHandler
from src.llm_app.api.llm_client import LLMClient


class TestTextProcessor:
    """Test cases for TextProcessor."""

    def test_init(self, temp_db):
        """Test initialization."""
        db = DatabaseManager(db_path=temp_db)
        processor = TextProcessor(db_manager=db)
        assert processor.db == db
        assert processor.llm_client is None

    def test_init_with_components(self, temp_db):
        """Test initialization with all components."""
        db = DatabaseManager(db_path=temp_db)
        file_handler = FileHandler(db_manager=db)
        llm_client = MagicMock(spec=LLMClient)

        processor = TextProcessor(
            db_manager=db,
            file_handler=file_handler,
            llm_client=llm_client
        )
        assert processor.db == db
        assert processor.file_handler == file_handler
        assert processor.llm_client == llm_client

    def test_set_llm_client(self, temp_db):
        """Test setting LLM client."""
        db = DatabaseManager(db_path=temp_db)
        processor = TextProcessor(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        processor.set_llm_client(llm_client)

        assert processor.llm_client == llm_client

    @patch('textract.process')
    def test_extract_text_success(self, mock_textract, temp_db):
        """Test successful text extraction."""
        mock_textract.return_value = b'Extracted text content'

        db = DatabaseManager(db_path=temp_db)
        processor = TextProcessor(db_manager=db)

        success, text = processor.extract_text('test.pdf')

        assert success is True
        assert 'Extracted text content' in text

    @patch('textract.process')
    def test_extract_text_failure(self, mock_textract, temp_db):
        """Test text extraction failure."""
        mock_textract.side_effect = Exception('Extraction error')

        db = DatabaseManager(db_path=temp_db)
        processor = TextProcessor(db_manager=db)

        success, text = processor.extract_text('test.pdf')

        assert success is False
        assert 'Extraction error' in text

    @patch('src.llm_app.core.file_handler.FileHandler.extract_text')
    def test_text_extraction_success(self, mock_extract, temp_db, mock_llm_response):
        """Test successful text extraction with categorization."""
        # Setup mocks
        mock_extract.return_value = {'result': 1, 'text': 'Sample content'}

        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = '{"研究背景": ["text"]}'
        processor.set_llm_client(llm_client)

        success, message, content = processor.text_extraction(
            'test.pdf',
            'test-uid'
        )

        assert success is True
        assert '成功' in message
        assert content is not None

    def test_text_extraction_no_llm_client(self, temp_db):
        """Test text extraction without LLM client."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        success, message, content = processor.text_extraction(
            'test.pdf',
            'test-uid'
        )

        assert success is False
        assert '未配置' in message
        assert content is None

    @patch('src.llm_app.core.file_handler.FileHandler.extract_text')
    def test_text_extraction_save_to_db(self, mock_extract, temp_db, mock_llm_response):
        """Test that extraction results are saved to database."""
        mock_extract.return_value = {'result': 1, 'text': 'Sample content'}

        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = '{"key": "value"}'
        processor.set_llm_client(llm_client)

        processor.text_extraction('test.pdf', 'test-uid')

        # Verify content is saved
        saved_content = db.get_content_by_uid('test-uid', 'file_extraction')
        assert saved_content is not None

    @patch('src.llm_app.core.file_handler.FileHandler.extract_text')
    def test_file_summary_success(self, mock_extract, temp_db):
        """Test successful file summary."""
        mock_extract.return_value = {'result': 1, 'text': 'Sample content'}

        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = 'This is a summary'
        processor.set_llm_client(llm_client)

        success, summary = processor.file_summary('test.pdf', 'test-uid')

        assert success is True
        assert summary == 'This is a summary'

    def test_file_summary_no_llm_client(self, temp_db):
        """Test file summary without LLM client."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        success, summary = processor.file_summary('test.pdf', 'test-uid')

        assert success is False
        assert '未配置' in summary

    @patch('src.llm_app.core.file_handler.FileHandler.extract_text')
    def test_file_summary_save_to_db(self, mock_extract, temp_db):
        """Test that summary is saved to database."""
        mock_extract.return_value = {'result': 1, 'text': 'Sample content'}

        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = 'Summary text'
        processor.set_llm_client(llm_client)

        processor.file_summary('test.pdf', 'test-uid')

        # Verify summary is saved
        saved_summary = db.get_content_by_uid('test-uid', 'file_summary')
        assert saved_summary == 'Summary text'

    @patch('src.llm_app.core.file_handler.FileHandler.extract_text')
    def test_generate_mindmap_success(self, mock_extract, temp_db):
        """Test successful mindmap generation."""
        mock_extract.return_value = {'result': 1, 'text': 'Sample content'}

        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = '''
        {
            "name": "Root",
            "children": [{"name": "Child", "children": []}]
        }
        '''
        processor.set_llm_client(llm_client)

        success, message, mindmap = processor.generate_mindmap(
            'test.pdf',
            'test-uid'
        )

        assert success is True
        assert '成功' in message
        assert mindmap['name'] == 'Root'

    def test_generate_mindmap_no_llm_client(self, temp_db):
        """Test mindmap generation without LLM client."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        success, message, mindmap = processor.generate_mindmap(
            'test.pdf',
            'test-uid'
        )

        assert success is False
        assert '未配置' in message
        assert mindmap is None

    @patch('src.llm_app.core.file_handler.FileHandler.extract_text')
    def test_generate_mindmap_save_to_db(self, mock_extract, temp_db):
        """Test that mindmap is saved to database."""
        mock_extract.return_value = {'result': 1, 'text': 'Sample content'}

        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = '{"name": "Root", "children": []}'
        processor.set_llm_client(llm_client)

        processor.generate_mindmap('test.pdf', 'test-uid')

        # Verify mindmap is saved
        saved_mindmap = db.get_content_by_uid('test-uid', 'file_mindmap')
        assert saved_mindmap is not None

    @patch('src.llm_app.core.file_handler.FileHandler.extract_text')
    def test_answer_question_success(self, mock_extract, temp_db):
        """Test successful question answering."""
        mock_extract.return_value = {'result': 1, 'text': 'Sample content'}

        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = 'This is the answer'
        processor.set_llm_client(llm_client)

        success, answer = processor.answer_question(
            'test.pdf',
            'What is this about?',
            'test-uid'
        )

        assert success is True
        assert answer == 'This is the answer'

    def test_answer_question_no_llm_client(self, temp_db):
        """Test question answering without LLM client."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        success, answer = processor.answer_question(
            'test.pdf',
            'What is this about?',
            'test-uid'
        )

        assert success is False
        assert '未配置' in answer

    def test_get_extracted_content(self, temp_db):
        """Test getting extracted content."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        # Save content
        import json
        content = {'key': 'value'}
        db.save_content_to_database(
            'test-uid',
            '/tmp/test.txt',
            json.dumps(content),
            'file_extraction'
        )

        # Get content
        result = processor.get_extracted_content('test-uid')

        assert result == content

    def test_get_extracted_content_none(self, temp_db):
        """Test getting non-existent extracted content."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        result = processor.get_extracted_content('nonexistent-uid')

        assert result is None

    def test_get_summary(self, temp_db):
        """Test getting summary."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        # Save summary
        db.save_content_to_database(
            'test-uid',
            '/tmp/test.txt',
            'Summary text',
            'file_summary'
        )

        result = processor.get_summary('test-uid')

        assert result == 'Summary text'

    def test_get_mindmap(self, temp_db):
        """Test getting mindmap."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        # Save mindmap
        import json
        mindmap = {'name': 'Root', 'children': []}
        db.save_content_to_database(
            'test-uid',
            '/tmp/test.txt',
            json.dumps(mindmap),
            'file_mindmap'
        )

        result = processor.get_mindmap('test-uid')

        assert result == mindmap

    def test_get_mindmap_invalid_json(self, temp_db):
        """Test getting mindmap with invalid JSON."""
        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        # Save invalid JSON
        db.save_content_to_database(
            'test-uid',
            '/tmp/test.txt',
            'invalid json',
            'file_mindmap'
        )

        result = processor.get_mindmap('test-uid')

        assert result is None

    @patch('src.llm_app.core.file_handler.FileHandler.extract_text')
    def test_text_extraction_error_handling(self, mock_extract, temp_db):
        """Test error handling in text extraction."""
        mock_extract.side_effect = Exception('File not found')

        db = DatabaseManager(db_path=temp_db)
        db.init_database()
        processor = TextProcessor(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        processor.set_llm_client(llm_client)

        success, message, content = processor.text_extraction(
            'nonexistent.pdf',
            'test-uid'
        )

        assert success is False
        assert '失败' in message
        assert content is None