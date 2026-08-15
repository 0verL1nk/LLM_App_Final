from agent.settings import load_agent_settings


def test_models_root_derives_model_cache_directories(monkeypatch, tmp_path):
    monkeypatch.delenv("LOCAL_RAG_EMBEDDING_CACHE_DIR", raising=False)
    monkeypatch.delenv("LOCAL_RAG_RERANK_CACHE_DIR", raising=False)
    monkeypatch.setenv("LOCAL_MODELS_ROOT", str(tmp_path))

    settings = load_agent_settings()

    assert settings.local_models_root == str(tmp_path)
    assert settings.local_embedding_cache_dir == f"{tmp_path}/embeddings"
    assert settings.local_rerank_cache_dir == f"{tmp_path}/flashrank"


def test_explicit_cache_overrides_keep_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_MODELS_ROOT", str(tmp_path))
    monkeypatch.setenv("LOCAL_RAG_EMBEDDING_CACHE_DIR", "custom/embed")

    settings = load_agent_settings()

    assert settings.local_embedding_cache_dir == "custom/embed"
