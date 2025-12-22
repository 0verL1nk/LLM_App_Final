"""
Pytest configuration and shared fixtures.
"""

import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        'username': 'testuser',
        'password': 'testpass123',
        'uuid': '550e8400-e29b-41d4-a716-446655440000',
        'api_key': 'test_api_key_123',
        'model_name': 'qwen-max'
    }


@pytest.fixture
def sample_file_data():
    """Sample file data for testing."""
    return {
        'original_filename': 'test_paper.pdf',
        'uid': 'file-uuid-123',
        'md5': 'd41d8cd98f00b204e9800998ecf8427e',
        'file_path': '/tmp/test_paper.pdf',
        'uuid': 'user-uuid-123',
        'created_at': '2024-01-01 00:00:00'
    }


@pytest.fixture
def mock_streamlit_session():
    """Mock Streamlit session state."""
    class MockSessionState:
        def __init__(self):
            self._state = {}

        def __getitem__(self, key):
            return self._state.get(key)

        def __setitem__(self, key, value):
            self._state[key] = value

        def get(self, key, default=None):
            return self._state.get(key, default)

    return MockSessionState()


@pytest.fixture
def sample_text_content():
    """Sample academic text content for testing."""
    return """
    研究背景:
    人工智能技术的快速发展正在改变我们的世界。在过去的十年中，深度学习、
    自然语言处理等领域取得了重大突破。然而，当前的研究仍面临诸多挑战。

    研究目的:
    本研究旨在探索一种新的方法来解决传统机器学习算法在处理大规模数据时的效率问题。
    我们希望通过优化算法架构，显著提升计算性能。

    研究方法:
    我们采用实验研究方法。首先设计了对比实验，使用标准数据集进行测试。
    然后收集性能指标，包括准确率、运行时间和内存使用情况。
    通过统计分析验证方法的有效性。

    研究结果:
    实验结果表明，我们提出的方法在保持准确率的同时，运行时间减少了40%，
    内存使用降低了35%。这证明了该方法的有效性。

    未来展望:
    未来研究可以进一步探索该方法在其他领域的应用，并优化算法的可扩展性。
    """


@pytest.fixture
def mock_llm_response():
    """Mock LLM API response."""
    return {
        "研究背景": [
            "人工智能技术的快速发展正在改变我们的世界。",
            "在过去的十年中，深度学习、自然语言处理等领域取得了重大突破。"
        ],
        "研究目的": [
            "本研究旨在探索一种新的方法来解决传统机器学习算法在处理大规模数据时的效率问题。"
        ],
        "研究方法": [
            "我们采用实验研究方法。",
            "首先设计了对比实验，使用标准数据集进行测试。"
        ],
        "研究结果": [
            "实验结果表明，我们提出的方法在保持准确率的同时，运行时间减少了40%。"
        ],
        "未来展望": [
            "未来研究可以进一步探索该方法在其他领域的应用。"
        ]
    }