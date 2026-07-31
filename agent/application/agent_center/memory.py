from agent.memory.consolidation import process_memory_event
from agent.memory.repository import create_memory_event
from utils.task_queue import enqueue_background_task


def enqueue_turn_memory_consolidation(
    *,
    user_uuid: str,
    project_uid: str,
    session_uid: str,
    prompt: str,
    answer: str,
) -> None:
    event_uid = create_memory_event(
        uuid=user_uuid,
        project_uid=project_uid,
        session_uid=session_uid,
        prompt=str(prompt or ""),
        answer=str(answer or ""),
    )
    if not event_uid:
        return
    enqueue_background_task(process_memory_event, event_uid)
