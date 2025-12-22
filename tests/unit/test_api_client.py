"""
Unit tests for LLMClient.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from src.llm_app.api.llm_client import LLMClient
from src.llm_app.config import Config


class TestLLMClient:
    """Test cases for LLMClient."""

    def test_init(self):
        """Test client initialization."""
        client = LLMClient(
            api_key='test_key',
            model_name='qwen-max',
            base_url='https://test.api'
        )
        assert client.api_key == 'test_key'
        assert client.model_name == 'qwen-max'
        assert client.base_url == 'https://test.api'

    def test_init_defaults(self):
        """Test initialization with defaults."""
        client = LLMClient(api_key='test_key')
        assert client.api_key == 'test_key'
        assert client.model_name == Config.DEFAULT_MODEL
        assert client.base_url == Config.API_BASE_URL

    @patch('openai.OpenAI')
    def test_client_creation(self, mock_openai):
        """Test OpenAI client creation."""
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance

        client = LLMClient(api_key='test_key')
        mock_openai.assert_called_once_with(
            api_key='test_key',
            base_url=Config.API_BASE_URL
        )

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_chat_completion_success(self, mock_openai_class):
        """Test successful chat completion."""
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Test response'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Test
        client = LLMClient(api_key='test_key')
        response = client.chat_completion([
            {'role': 'user', 'content': 'test'}
        ])

        assert response == 'Test response'
        mock_client.chat.completions.create.assert_called_once()

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_chat_completion_with_params(self, mock_openai_class):
        """Test chat completion with parameters."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Test response'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = LLMClient(api_key='test_key')
        response = client.chat_completion(
            [{'role': 'user', 'content': 'test'}],
            temperature=0.5,
            max_tokens=100
        )

        assert response == 'Test response'
        mock_client.chat.completions.create.assert_called_once_with(
            model=Config.DEFAULT_MODEL,
            messages=[{'role': 'user', 'content': 'test'}],
            temperature=0.5,
            max_tokens=100
        )

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_chat_completion_error(self, mock_openai_class):
        """Test chat completion error handling."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception('API Error')
        mock_openai_class.return_value = mock_client

        client = LLMClient(api_key='test_key')
        with pytest.raises(Exception) as exc_info:
            client.chat_completion([{'role': 'user', 'content': 'test'}])

        assert 'API Error' in str(exc_info.value)

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_stream_completion(self, mock_openai_class):
        """Test streaming completion."""
        mock_client = MagicMock()

        # Mock streaming response
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content='chunk1'))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content='chunk2'))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
        ]
        mock_client.chat.completions.create.return_value = iter(chunks)
        mock_openai_class.return_value = mock_client

        client = LLMClient(api_key='test_key')
        result = list(client.stream_completion([{'role': 'user', 'content': 'test'}]))

        assert result == ['chunk1', 'chunk2']

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_extract_text_from_paper(self, mock_openai_class):
        """Test text extraction from paper."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"key": "value"}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = LLMClient(api_key='test_key')
        result = client.extract_text_from_paper('Sample paper content')

        assert result == {'key': 'value'}

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_extract_text_with_markdown_code(self, mock_openai_class):
        """Test JSON extraction from markdown code block."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '```json\n{"key": "value"}\n```'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = LLMClient(api_key='test_key')
        result = client.extract_text_from_paper('Sample content')

        assert result == {'key': 'value'}

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_generate_paper_summary(self, mock_openai_class):
        """Test paper summary generation."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'This is a summary of the paper.'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = LLMClient(api_key='test_key')
        summary = client.generate_paper_summary('Sample paper content')

        assert summary == 'This is a summary of the paper.'

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_answer_question(self, mock_openai_class):
        """Test question answering."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'This is the answer to your question.'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = LLMClient(api_key='test_key')
        answer = client.answer_question('Paper content', 'What is the main topic?')

        assert answer == 'This is the answer to your question.'

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_optimize_text(self, mock_openai_class):
        """Test text optimization."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '#### 优化后的文本\nOptimized content here'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = LLMClient(api_key='test_key')
        optimized = client.optimize_text('Original text')

        assert 'Optimized content here' in optimized

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_generate_mindmap_data(self, mock_openai_class):
        """Test mindmap generation."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''
        {
            "name": "Root",
            "children": [
                {"name": "Child1", "children": []},
                {"name": "Child2", "children": []}
            ]
        }
        '''
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = LLMClient(api_key='test_key')
        mindmap = client.generate_mindmap_data('Sample content')

        assert mindmap['name'] == 'Root'
        assert len(mindmap['children']) == 2

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_translate_text(self, mock_openai_class):
        """Test text translation."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Translated text in English'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        client = LLMClient(api_key='test_key')
        translated = client.translate_text('原始文本', 'English')

        assert translated == 'Translated text in English'

    def test_parse_json_response_valid(self):
        """Test parsing valid JSON response."""
        client = LLMClient(api_key='test_key')
        result = client._parse_json_response('{"key": "value"}')

        assert result == {'key': 'value'}

    def test_parse_json_response_with_markdown(self):
        """Test parsing JSON response with markdown."""
        client = LLMClient(api_key='test_key')
        result = client._parse_json_response('```json\n{"key": "value"}\n```')

        assert result == {'key': 'value'}

    def test_parse_json_response_invalid(self):
        """Test parsing invalid JSON response."""
        client = LLMClient(api_key='test_key')
        result = client._parse_json_response('invalid json')

        # Should return fallback structure
        assert result['name'] == '解析失败'
        assert 'children' in result

    def test_parse_json_response_empty(self):
        """Test parsing empty response."""
        client = LLMClient(api_key='test_key')
        result = client._parse_json_response('')

        # Should return fallback structure
        assert result['name'] == '解析失败'

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_different_model_names(self, mock_openai_class):
        """Test using different model names."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Response'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        models = ['qwen-max', 'qwen-plus', 'qwen-turbo']
        for model in models:
            client = LLMClient(api_key='test_key', model_name=model)
            client.chat_completion([{'role': 'user', 'content': 'test'}])

            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]['model'] == model

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_custom_base_url(self, mock_openai_class):
        """Test using custom base URL."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        custom_url = 'https://custom.api.endpoint'
        client = LLMClient(
            api_key='test_key',
            base_url=custom_url
        )

        mock_openai_class.assert_called_once_with(
            api_key='test_key',
            base_url=custom_url
        )

    @patch('src.llm_app.api.llm_client.OpenAI')
    def test_streaming_error_handling(self, mock_openai_class):
        """Test streaming error handling."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception('Stream error')
        mock_openai_class.return_value = mock_client

        client = LLMClient(api_key='test_key')
        with pytest.raises(Exception) as exc_info:
            list(client.stream_completion([{'role': 'user', 'content': 'test'}]))

        assert 'Stream error' in str(exc_info.value)

    def test_logger_configuration(self):
        """Test logger is properly configured."""
        client = LLMClient(api_key='test_key')
        assert client.logger is not None
        assert client.logger.name == 'src.llm_app.api.llm_client'