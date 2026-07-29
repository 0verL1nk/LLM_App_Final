from typing import Annotated

from fastapi import Header

from agent.adapters.sqlite.user_repository import ensure_local_api_user


def current_user_id(x_user_id: Annotated[str | None, Header()] = None) -> str:
    user_uuid = str(x_user_id or "local-user").strip() or "local-user"
    ensure_local_api_user(user_uuid)
    return user_uuid
