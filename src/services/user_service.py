"""
User service for profile management and configuration.
"""

import httpx
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from core.logger import get_logger
from core.config import settings

logger = get_logger(__name__)

VALID_MODELS = [
    "qwen-max",
    "qwen-plus",
    "qwen-turbo",
    "qwen-long",
    "qwen-vl-max",
    "qwen-vl-plus",
]


class UserService:
    """Service for user profile management operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_profile(self, user_uuid: str) -> Optional[User]:
        """
        Get user profile by UUID.

        Args:
            user_uuid: User's UUID

        Returns:
            User object or None if not found
        """
        query = select(User).where(User.uuid == user_uuid)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_api_key(
        self,
        user_uuid: str,
        api_key: str,
        validate: bool = True,
    ) -> Dict[str, Any]:
        """
        Update user's DashScope API key.

        Args:
            user_uuid: User's UUID
            api_key: New API key
            validate: Whether to validate the API key

        Returns:
            Dict with success status and message
        """
        user = await self.get_user_profile(user_uuid)
        if not user:
            return {"success": False, "message": "User not found"}

        if validate:
            is_valid = await self.validate_dashscope_api_key(api_key)
            if not is_valid:
                return {
                    "success": False,
                    "message": "Invalid API key - validation failed",
                    "error_code": "API_KEY_INVALID",
                }

        user.api_key = api_key
        user.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"Updated API key for user {user_uuid}")

        return {
            "success": True,
            "message": "API key updated successfully",
            "api_key_configured": True,
        }

    async def update_preferences(
        self,
        user_uuid: str,
        preferred_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update user preferences.

        Args:
            user_uuid: User's UUID
            preferred_model: New preferred LLM model

        Returns:
            Dict with success status and updated preferences
        """
        user = await self.get_user_profile(user_uuid)
        if not user:
            return {"success": False, "message": "User not found"}

        updated_fields = []

        if preferred_model is not None:
            if preferred_model not in VALID_MODELS:
                return {
                    "success": False,
                    "message": f"Invalid model. Valid models: {', '.join(VALID_MODELS)}",
                    "error_code": "INVALID_MODEL",
                }
            user.preferred_model = preferred_model
            updated_fields.append("preferred_model")

        if updated_fields:
            user.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(user)

            logger.info(
                f"Updated preferences for user {user_uuid}: {', '.join(updated_fields)}"
            )

        return {
            "success": True,
            "message": "Preferences updated successfully",
            "preferred_model": user.preferred_model,
        }

    async def validate_dashscope_api_key(self, api_key: str) -> bool:
        """
        Validate a DashScope API key by making a test request.

        Args:
            api_key: API key to validate

        Returns:
            True if valid, False otherwise
        """
        if not api_key or len(api_key.strip()) < 20:
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "qwen-turbo",
                        "input": {"messages": [{"role": "user", "content": "hi"}]},
                        "parameters": {
                            "max_tokens": 1,
                        },
                    },
                )

                if response.status_code == 200:
                    return True
                elif response.status_code in [401, 403]:
                    logger.warning(f"API key validation failed: {response.status_code}")
                    return False
                else:
                    logger.info(
                        f"API key validation returned {response.status_code}, assuming valid"
                    )
                    return True

        except httpx.TimeoutException:
            logger.warning("API key validation timed out, assuming valid")
            return True
        except Exception as e:
            logger.error(f"API key validation error: {e}")
            return True

    async def clear_api_key(self, user_uuid: str) -> Dict[str, Any]:
        """
        Clear user's API key.

        Args:
            user_uuid: User's UUID

        Returns:
            Dict with success status
        """
        user = await self.get_user_profile(user_uuid)
        if not user:
            return {"success": False, "message": "User not found"}

        user.api_key = None
        user.updated_at = datetime.utcnow()

        await self.db.commit()

        logger.info(f"Cleared API key for user {user_uuid}")

        return {
            "success": True,
            "message": "API key cleared successfully",
            "api_key_configured": False,
        }

    async def get_user_stats(self, user_uuid: str) -> Dict[str, Any]:
        """
        Get user statistics.

        Args:
            user_uuid: User's UUID

        Returns:
            Dict with user statistics
        """
        user = await self.get_user_profile(user_uuid)
        if not user:
            return {"success": False, "message": "User not found"}

        file_count = len(user.files) if user.files else 0
        task_count = len(user.tasks) if user.tasks else 0

        return {
            "success": True,
            "data": {
                "file_count": file_count,
                "task_count": task_count,
                "created_at": user.created_at,
                "api_key_configured": user.has_api_key,
            },
        }
