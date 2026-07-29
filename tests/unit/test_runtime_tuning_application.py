from agent.application.runtime_tuning import apply_runtime_tuning_env


def test_apply_runtime_tuning_env_sets_and_clears_values():
    environ = {
        "RAG_INDEX_BATCH_SIZE": "128",
    }
    apply_runtime_tuning_env(
        settings={
            "rag_index_batch_size": None,
            "local_rag_project_max_chars": None,
            "local_rag_project_max_chunks": 50,
        },
        environ=environ,
    )

    assert "RAG_INDEX_BATCH_SIZE" not in environ
    assert environ["LOCAL_RAG_PROJECT_MAX_CHUNKS"] == "50"
