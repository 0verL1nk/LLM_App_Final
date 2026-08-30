import pytest

from agent.rag.fastembed_runtime import build_fastembed_embeddings

_MODEL = "Qdrant/bge-small-zh-v1.5"
_CACHE_DIR_NAME = "models--Qdrant--bge-small-zh-v1.5"


def test_partial_download_cache_is_cleared_and_retried(monkeypatch, tmp_path):
    cache_dir = tmp_path / "embeddings"
    stale_snapshot = cache_dir / _CACHE_DIR_NAME / "snapshots" / "abc"
    stale_snapshot.mkdir(parents=True)
    (stale_snapshot / "refs").write_text("abc", encoding="utf-8")

    calls = []

    def fake_ctor(*, model_name, cache_dir):
        calls.append((model_name, cache_dir))
        if len(calls) == 1:
            raise Exception(
                "NO_SUCHFILE : 3 : Load model from model_optimized.onnx failed. File doesn't exist"
            )
        return object()

    monkeypatch.setattr("langchain_community.embeddings.fastembed.FastEmbedEmbeddings", fake_ctor)

    result = build_fastembed_embeddings(model_name=_MODEL, cache_dir=str(cache_dir))

    assert result is not None
    assert len(calls) == 2
    assert not (cache_dir / _CACHE_DIR_NAME).exists()


def test_unrelated_errors_are_raised_without_cache_wipe(monkeypatch, tmp_path):
    cache_dir = tmp_path / "embeddings"
    snapshot = cache_dir / _CACHE_DIR_NAME
    snapshot.mkdir(parents=True)

    def fake_ctor(**_kwargs):
        raise Exception("CUDA execution provider failure")

    monkeypatch.setattr("langchain_community.embeddings.fastembed.FastEmbedEmbeddings", fake_ctor)

    with pytest.raises(Exception, match="CUDA"):
        build_fastembed_embeddings(model_name=_MODEL, cache_dir=str(cache_dir))

    assert snapshot.exists()
