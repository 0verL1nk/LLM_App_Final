from agent.adapters.orm.database import run_migrations
from agent.adapters.orm.memory_repository import delete_memory_item, list_memory_items, upsert_memory_item


def test_l3_is_project_scoped_and_l4_is_user_scoped(tmp_path) -> None:
    database = str(tmp_path / "runtime.sqlite")
    run_migrations(database)
    project_memory = upsert_memory_item(
        uuid="user", project_uid="project-a", level="L3", memory_type="semantic",
        content="project fact", db_name=database,
    )
    preference = upsert_memory_item(
        uuid="user", project_uid="project-a", level="L4", memory_type="preference",
        content="prefer concise answers", db_name=database,
    )

    assert [item["memory_uid"] for item in list_memory_items(
        uuid="user", project_uid="project-b", level="L3", db_name=database
    )] == []
    assert [item["memory_uid"] for item in list_memory_items(
        uuid="user", project_uid="project-b", level="L4", db_name=database
    )] == [preference]
    assert delete_memory_item(
        memory_uid=project_memory, uuid="user", project_uid="project-b", level="L3", db_name=database
    ) is False
