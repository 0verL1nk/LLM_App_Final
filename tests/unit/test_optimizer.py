"""
Unit tests for TextOptimizer.
"""

import pytest
from unittest.mock import MagicMock

from src.llm_app.core.optimizer import TextOptimizer
from src.llm_app.core.database import DatabaseManager
from src.llm_app.api.llm_client import LLMClient


class TestTextOptimizer:
    """Test cases for TextOptimizer."""

    def test_init(self, temp_db):
        """Test initialization."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)
        assert optimizer.db == db
        assert optimizer.llm_client is None

    def test_set_llm_client(self, temp_db):
        """Test setting LLM client."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        optimizer.set_llm_client(llm_client)

        assert optimizer.llm_client == llm_client

    def test_optimize_text_no_client(self, temp_db):
        """Test text optimization without LLM client."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        success, result = optimizer.optimize_text('Original text')

        assert success is False
        assert '未配置' in result

    def test_optimize_text_success(self, temp_db):
        """Test successful text optimization."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.optimize_text.return_value = '#### 优化后的文本\nOptimized content'
        optimizer.set_llm_client(llm_client)

        success, result = optimizer.optimize_text('Original text')

        assert success is True
        assert 'Optimized content' in result

    def test_reduce_similarity_no_client(self, temp_db):
        """Test similarity reduction without LLM client."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        success, result = optimizer.reduce_similarity('Original text')

        assert success is False
        assert '未配置' in result

    def test_reduce_similarity_success(self, temp_db):
        """Test successful similarity reduction."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = 'Paraphrased content'
        optimizer.set_llm_client(llm_client)

        success, result = optimizer.reduce_similarity('Original text')

        assert success is True
        assert result == 'Paraphrased content'

    def test_translate_text_no_client(self, temp_db):
        """Test translation without LLM client."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        success, result = optimizer.translate_text('原始文本', 'English')

        assert success is False
        assert '未配置' in result

    def test_translate_text_success(self, temp_db):
        """Test successful translation."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.translate_text.return_value = 'Translated text'
        optimizer.set_llm_client(llm_client)

        success, result = optimizer.translate_text('原始文本', 'English')

        assert success is True
        assert result == 'Translated text'

    def test_improve_clarity_no_client(self, temp_db):
        """Test clarity improvement without LLM client."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        success, result = optimizer.improve_clarity('Unclear text')

        assert success is False
        assert '未配置' in result

    def test_improve_clarity_success(self, temp_db):
        """Test successful clarity improvement."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = 'Clear and improved text'
        optimizer.set_llm_client(llm_client)

        success, result = optimizer.improve_clarity('Unclear text')

        assert success is True
        assert result == 'Clear and improved text'

    def test_enhance_academic_style_no_client(self, temp_db):
        """Test academic style enhancement without LLM client."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        success, result = optimizer.enhance_academic_style('Informal text')

        assert success is False
        assert '未配置' in result

    def test_enhance_academic_style_success(self, temp_db):
        """Test successful academic style enhancement."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = 'Formal academic text'
        optimizer.set_llm_client(llm_client)

        success, result = optimizer.enhance_academic_style('Informal text')

        assert success is True
        assert result == 'Formal academic text'

    def test_expand_content_no_client(self, temp_db):
        """Test content expansion without LLM client."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        success, result = optimizer.expand_content('Short text', 1.5)

        assert success is False
        assert '未配置' in result

    def test_expand_content_success(self, temp_db):
        """Test successful content expansion."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = 'Expanded text content with details'
        optimizer.set_llm_client(llm_client)

        success, result = optimizer.expand_content('Short text', 1.5)

        assert success is True
        assert result == 'Expanded text content with details'

    def test_summarize_content_no_client(self, temp_db):
        """Test content summarization without LLM client."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        success, result = optimizer.summarize_content('Long text', 100)

        assert success is False
        assert '未配置' in result

    def test_summarize_content_success(self, temp_db):
        """Test successful content summarization."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = 'Brief summary'
        optimizer.set_llm_client(llm_client)

        success, result = optimizer.summarize_content('Long text', 100)

        assert success is True
        assert result == 'Brief summary'

    def test_expand_content_different_ratios(self, temp_db):
        """Test content expansion with different ratios."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = 'Expanded'
        optimizer.set_llm_client(llm_client)

        ratios = [1.0, 1.5, 2.0, 3.0]
        for ratio in ratios:
            success, result = optimizer.expand_content('Text', ratio)
            assert success is True

    def test_optimization_error_handling(self, temp_db):
        """Test error handling in optimization."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.optimize_text.side_effect = Exception('API error')
        optimizer.set_llm_client(llm_client)

        success, result = optimizer.optimize_text('Text')

        assert success is False
        assert '失败' in result

    def test_multiple_optimizations(self, temp_db):
        """Test multiple optimization operations."""
        db = DatabaseManager(db_path=temp_db)
        optimizer = TextOptimizer(db_manager=db)

        llm_client = MagicMock(spec=LLMClient)
        llm_client.chat_completion.return_value = 'Result'
        optimizer.set_llm_client(llm_client)

        # Test all optimization methods
        operations = [
            ('optimize', lambda: optimizer.optimize_text('Text')),
            ('reduce', lambda: optimizer.reduce_similarity('Text')),
            ('translate', lambda: optimizer.translate_text('Text', 'English')),
            ('clarity', lambda: optimizer.improve_clarity('Text')),
            ('academic', lambda: optimizer.enhance_academic_style('Text')),
            ('expand', lambda: optimizer.expand_content('Text', 1.5)),
            ('summarize', lambda: optimizer.summarize_content('Text', 100)),
        ]

        for name, operation in operations:
            success, result = operation()
            assert success is True, f"{name} operation failed"