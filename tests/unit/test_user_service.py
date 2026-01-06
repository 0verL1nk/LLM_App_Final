"""
Unit tests for UserService.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import sys

sys.path.insert(0, "/home/ling/LLM_App_Final/src")

from llm_app.services.user_service import UserService, VALID_MODELS


class TestUserService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.fixture
    def user_service(self, mock_db):
        return UserService(mock_db)

    @pytest.fixture
    def sample_user(self):
        user = MagicMock()
        user.uuid = "user-uuid-123"
        user.username = "testuser"
        user.email = "test@example.com"
        user.api_key = None
        user.preferred_model = "qwen-max"
        user.created_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        user.files = []
        user.tasks = []
        user.has_api_key = False
        return user

    def setup_db_return(self, mock_db, return_value):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = return_value
        mock_db.execute = AsyncMock(return_value=mock_result)

    @pytest.mark.asyncio
    async def test_get_user_profile_success(self, user_service, mock_db, sample_user):
        self.setup_db_return(mock_db, sample_user)

        user = await user_service.get_user_profile("user-uuid-123")

        assert user == sample_user
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_profile_not_found(self, user_service, mock_db):
        self.setup_db_return(mock_db, None)

        user = await user_service.get_user_profile("nonexistent")
        assert user is None

    @pytest.mark.asyncio
    async def test_update_api_key_success_no_validation(
        self, user_service, mock_db, sample_user
    ):
        self.setup_db_return(mock_db, sample_user)

        result = await user_service.update_api_key(
            user_uuid="user-uuid-123",
            api_key="sk-new-api-key-12345678901234567890",
            validate=False,
        )

        assert result["success"] is True
        assert result["api_key_configured"] is True
        assert sample_user.api_key == "sk-new-api-key-12345678901234567890"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_api_key_user_not_found(self, user_service, mock_db):
        self.setup_db_return(mock_db, None)

        result = await user_service.update_api_key(
            user_uuid="nonexistent",
            api_key="sk-test-key",
            validate=False,
        )

        assert result["success"] is False
        assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_update_api_key_with_validation_success(
        self, user_service, mock_db, sample_user
    ):
        self.setup_db_return(mock_db, sample_user)

        with patch.object(
            user_service, "validate_dashscope_api_key", return_value=True
        ):
            result = await user_service.update_api_key(
                user_uuid="user-uuid-123",
                api_key="sk-valid-key-12345678901234567890",
                validate=True,
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_api_key_with_validation_failure(
        self, user_service, mock_db, sample_user
    ):
        self.setup_db_return(mock_db, sample_user)

        with patch.object(
            user_service, "validate_dashscope_api_key", return_value=False
        ):
            result = await user_service.update_api_key(
                user_uuid="user-uuid-123",
                api_key="invalid-key",
                validate=True,
            )

        assert result["success"] is False
        assert result["error_code"] == "API_KEY_INVALID"
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_preferences_model_success(
        self, user_service, mock_db, sample_user
    ):
        self.setup_db_return(mock_db, sample_user)

        result = await user_service.update_preferences(
            user_uuid="user-uuid-123",
            preferred_model="qwen-plus",
        )

        assert result["success"] is True
        assert result["preferred_model"] == "qwen-plus"
        assert sample_user.preferred_model == "qwen-plus"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_preferences_invalid_model(
        self, user_service, mock_db, sample_user
    ):
        self.setup_db_return(mock_db, sample_user)

        result = await user_service.update_preferences(
            user_uuid="user-uuid-123",
            preferred_model="invalid-model",
        )

        assert result["success"] is False
        assert result["error_code"] == "INVALID_MODEL"
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_preferences_user_not_found(self, user_service, mock_db):
        self.setup_db_return(mock_db, None)

        result = await user_service.update_preferences(
            user_uuid="nonexistent",
            preferred_model="qwen-max",
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_update_preferences_no_changes(
        self, user_service, mock_db, sample_user
    ):
        self.setup_db_return(mock_db, sample_user)

        result = await user_service.update_preferences(
            user_uuid="user-uuid-123",
            preferred_model=None,
        )

        assert result["success"] is True
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_preferences_all_valid_models(
        self, user_service, mock_db, sample_user
    ):
        for model in VALID_MODELS:
            self.setup_db_return(mock_db, sample_user)
            mock_db.commit.reset_mock()

            result = await user_service.update_preferences(
                user_uuid="user-uuid-123",
                preferred_model=model,
            )
            assert result["success"] is True, f"Model {model} should be valid"

    @pytest.mark.asyncio
    async def test_validate_api_key_too_short(self, user_service):
        result = await user_service.validate_dashscope_api_key("short")
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_api_key_empty(self, user_service):
        result = await user_service.validate_dashscope_api_key("")
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_api_key_none(self, user_service):
        result = await user_service.validate_dashscope_api_key(None)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_api_key_whitespace_only(self, user_service):
        result = await user_service.validate_dashscope_api_key("   ")
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_api_key_http_success(self, user_service):
        with patch("services.user_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_context = AsyncMock()
            mock_context.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await user_service.validate_dashscope_api_key(
                "sk-valid-key-12345678901234567890"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_api_key_http_401(self, user_service):
        with patch("services.user_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_context = AsyncMock()
            mock_context.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await user_service.validate_dashscope_api_key(
                "sk-invalid-key-12345678901234567"
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_api_key_http_403(self, user_service):
        with patch("services.user_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_context = AsyncMock()
            mock_context.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await user_service.validate_dashscope_api_key(
                "sk-forbidden-key-12345678901234"
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_api_key_timeout(self, user_service):
        import httpx

        with patch("services.user_service.httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_context)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await user_service.validate_dashscope_api_key(
                "sk-timeout-key-12345678901234567"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_clear_api_key_success(self, user_service, mock_db, sample_user):
        sample_user.api_key = "sk-existing-key"
        self.setup_db_return(mock_db, sample_user)

        result = await user_service.clear_api_key("user-uuid-123")

        assert result["success"] is True
        assert result["api_key_configured"] is False
        assert sample_user.api_key is None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_api_key_user_not_found(self, user_service, mock_db):
        self.setup_db_return(mock_db, None)

        result = await user_service.clear_api_key("nonexistent")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_user_stats_success(self, user_service, mock_db, sample_user):
        sample_user.files = [MagicMock(), MagicMock(), MagicMock()]
        sample_user.tasks = [MagicMock(), MagicMock()]
        sample_user.has_api_key = True
        self.setup_db_return(mock_db, sample_user)

        result = await user_service.get_user_stats("user-uuid-123")

        assert result["success"] is True
        assert result["data"]["file_count"] == 3
        assert result["data"]["task_count"] == 2
        assert result["data"]["api_key_configured"] is True

    @pytest.mark.asyncio
    async def test_get_user_stats_user_not_found(self, user_service, mock_db):
        self.setup_db_return(mock_db, None)

        result = await user_service.get_user_stats("nonexistent")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_user_stats_empty_user(self, user_service, mock_db, sample_user):
        sample_user.files = None
        sample_user.tasks = None
        self.setup_db_return(mock_db, sample_user)

        result = await user_service.get_user_stats("user-uuid-123")

        assert result["success"] is True
        assert result["data"]["file_count"] == 0
        assert result["data"]["task_count"] == 0
