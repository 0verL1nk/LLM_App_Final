from agent.adapters.lancedb.rag_index import (
    document_index_exists,
    publish_document_index,
    search_published_chunks,
)


def _publish(*, version: str, doc_uid: str, text: str) -> None:
    publish_document_index(
        project_uid="p1",
        doc_uid=doc_uid,
        doc_name=f"{doc_uid}.pdf",
        index_version=version,
        chunks=[text, "dense vector retrieval"],
        metadatas=[{"start_index": 0}, {"start_index": len(text)}],
        embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
    )


def test_lancedb_publish_is_idempotent_and_searches_ready_versions(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_LANCEDB_DIR", str(tmp_path / "lancedb"))
    monkeypatch.setenv("LANCEDB_VECTOR_INDEX_MIN_ROWS", "100000")
    _publish(version="settings1:hash1", doc_uid="d1", text="混合检索与向量数据库")
    _publish(version="settings1:hash1", doc_uid="d1", text="混合检索与向量数据库")
    _publish(version="settings1:staging", doc_uid="d2", text="不应出现的暂存版本")

    assert document_index_exists(
        project_uid="p1",
        doc_uid="d1",
        index_version="settings1:hash1",
    )
    rows = search_published_chunks(
        project_uid="p1",
        ready_versions=[("d1", "settings1:hash1")],
        query="混合检索",
        query_vector=[1.0, 0.0, 0.0],
        limit=10,
    )

    assert len(rows) == 2
    assert {row["doc_uid"] for row in rows} == {"d1"}
    assert rows[0]["text"] == "混合检索与向量数据库"
    assert isinstance(rows[0]["_relevance_score"], float)


def test_lancedb_index_existence_is_scoped_by_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_LANCEDB_DIR", str(tmp_path / "lancedb"))
    monkeypatch.setenv("LANCEDB_VECTOR_INDEX_MIN_ROWS", "100000")
    _publish(version="settings2:hash1", doc_uid="d1", text="paper evidence")

    assert not document_index_exists(
        project_uid="another-project",
        doc_uid="d1",
        index_version="settings2:hash1",
    )
