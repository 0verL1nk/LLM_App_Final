"""User model and indexing configuration use cases."""

from typing import Any

from ..adapters.user_settings import (
    apply_runtime_tuning_env_for_user,
    read_api_key_for_user,
    read_base_url_for_user,
    read_model_name_for_user,
    read_runtime_tuning_settings_for_user,
    save_api_key_for_user,
    save_base_url_for_user,
    save_model_name_for_user,
    save_runtime_tuning_settings_for_user,
)


def read_user_configuration(*, user_uuid: str) -> dict[str, Any]:
    tuning = read_runtime_tuning_settings_for_user(uuid=user_uuid)
    api_key = read_api_key_for_user(uuid=user_uuid)
    return {
        "api_key_configured": bool(api_key),
        "api_key_hint": f"••••{api_key[-4:]}" if api_key else "",
        "model_name": read_model_name_for_user(uuid=user_uuid) or "",
        "base_url": read_base_url_for_user(uuid=user_uuid) or "",
        **tuning,
    }


def save_user_configuration(
    *,
    user_uuid: str,
    api_key: str | None,
    model_name: str,
    base_url: str,
    rag_index_batch_size: int | None,
    local_rag_project_max_chars: int | None,
    local_rag_project_max_chunks: int | None,
) -> dict[str, Any]:
    if api_key is not None and api_key.strip():
        save_api_key_for_user(uuid=user_uuid, api_key=api_key.strip())
    save_model_name_for_user(uuid=user_uuid, model_name=model_name.strip())
    save_base_url_for_user(uuid=user_uuid, base_url=base_url.strip() or None)
    save_runtime_tuning_settings_for_user(
        user_uuid,
        rag_index_batch_size=rag_index_batch_size,
        local_rag_project_max_chars=local_rag_project_max_chars,
        local_rag_project_max_chunks=local_rag_project_max_chunks,
    )
    apply_runtime_tuning_env_for_user(uuid=user_uuid)
    return read_user_configuration(user_uuid=user_uuid)


__all__ = ["read_user_configuration", "save_user_configuration"]
