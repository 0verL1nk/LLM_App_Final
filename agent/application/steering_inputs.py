"""Use cases for steering an active research Run."""

from __future__ import annotations

from typing import Any

from ..adapters.orm.run_repository import append_run_item_event
from ..adapters.orm.steering_input_repository import (
    claim_queued_steering_inputs,
    confirm_steering_inputs,
    enqueue_steering_input,
    list_delivered_steering_inputs,
    list_unconfirmed_steering_inputs,
    requeue_delivering_steering_inputs,
    transfer_unconfirmed_steering_inputs,
)
from ..domain.agent_task import RunItemStatus, RunItemType


def queue_steering_input(**kwargs: Any) -> tuple[dict[str, Any], bool]:
    """Persist a user follow-up and expose it as a V2 queue item."""
    input_item, created = enqueue_steering_input(**kwargs)
    if created:
        append_run_item_event(
            run_uid=str(input_item["run_uid"]),
            item_uid=_item_uid(str(input_item["run_uid"]), str(input_item["input_uid"])),
            item_type=RunItemType.HUMAN_REQUEST.value,
            status=RunItemStatus.IN_PROGRESS.value,
            event_type="item.created",
            payload={"inputId": input_item["input_uid"], "text": input_item["text"], "state": "queued"},
            db_name=str(kwargs.get("db_name") or "./database.sqlite"),
        )
    return input_item, created


def claim_steering_inputs_for_model(*, run_uid: str, db_name: str = "./database.sqlite") -> list[dict[str, Any]]:
    """Recover incomplete delivery then claim the batch for a single model call."""
    requeue_delivering_steering_inputs(run_uid=run_uid, db_name=db_name)
    return claim_queued_steering_inputs(run_uid=run_uid, db_name=db_name)


def confirm_steering_inputs_for_model(*, run_uid: str, inputs: list[dict[str, Any]], db_name: str = "./database.sqlite") -> None:
    """Mark a successfully consumed batch terminal and update its V2 projection."""
    input_uids = [str(item["input_uid"]) for item in inputs]
    confirmed = set(confirm_steering_inputs(run_uid=run_uid, input_uids=input_uids, db_name=db_name))
    for input_item in inputs:
        if str(input_item["input_uid"]) not in confirmed:
            continue
        append_run_item_event(
            run_uid=run_uid,
            item_uid=_item_uid(run_uid, str(input_item["input_uid"])),
            item_type=RunItemType.HUMAN_REQUEST.value,
            status=RunItemStatus.COMPLETED.value,
            event_type="item.completed",
            payload={"inputId": input_item["input_uid"], "text": input_item["text"], "state": "delivered"},
            db_name=db_name,
        )


def delivered_steering_inputs(*, run_uid: str, db_name: str = "./database.sqlite") -> list[dict[str, Any]]:
    """Return inputs confirmed by a successful model call."""
    return list_delivered_steering_inputs(run_uid=run_uid, db_name=db_name)


def unconfirmed_steering_inputs(*, run_uid: str, db_name: str = "./database.sqlite") -> list[dict[str, Any]]:
    """Return inputs that require a successor Run after a terminal boundary."""
    return list_unconfirmed_steering_inputs(run_uid=run_uid, db_name=db_name)


def move_unconfirmed_inputs_to_followup(
    *, source_run_uid: str, target_run_uid: str, db_name: str = "./database.sqlite"
) -> list[dict[str, Any]]:
    """Project forwarded inputs out of a terminal Run and into its successor."""
    moved = transfer_unconfirmed_steering_inputs(
        source_run_uid=source_run_uid, target_run_uid=target_run_uid, db_name=db_name
    )
    for input_item in moved:
        input_uid = str(input_item["input_uid"])
        text = str(input_item["text"])
        append_run_item_event(
            run_uid=source_run_uid,
            item_uid=_item_uid(source_run_uid, input_uid),
            item_type=RunItemType.HUMAN_REQUEST.value,
            status=RunItemStatus.COMPLETED.value,
            event_type="item.completed",
            payload={"inputId": input_uid, "text": text, "state": "forwarded"},
            db_name=db_name,
        )
        append_run_item_event(
            run_uid=target_run_uid,
            item_uid=_item_uid(target_run_uid, input_uid),
            item_type=RunItemType.HUMAN_REQUEST.value,
            status=RunItemStatus.IN_PROGRESS.value,
            event_type="item.created",
            payload={"inputId": input_uid, "text": text, "state": "queued"},
            db_name=db_name,
        )
    return moved


def _item_uid(run_uid: str, input_uid: str) -> str:
    return f"item_steering_input_{run_uid}_{input_uid}"


__all__ = [
    "claim_steering_inputs_for_model",
    "confirm_steering_inputs_for_model",
    "delivered_steering_inputs",
    "move_unconfirmed_inputs_to_followup",
    "unconfirmed_steering_inputs",
    "queue_steering_input",
]
