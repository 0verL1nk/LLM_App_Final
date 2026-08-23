import sqlite3

from agent.adapters.rag import DynamicProjectEvidenceService
from agent.adapters.sqlite.rag_ingestion_repository import (
    get_document_text,
    get_ingestion,
    init_rag_ingestion_tables,
    list_ready_project_documents,
    queue_ingestion,
    save_document_text,
    update_ingestion_progress,
)
from agent.application.rag_ingestion import (
    enqueue_document_ingestion,
    should_requeue_ingestion,
)
from agent.rag.hybrid import (
    build_project_document_index_with_settings,
)


def _init_project_binding(db_name: str) -> None:
    with sqlite3.connect(db_name) as conn:
        conn.execute(
            """
            CREATE TABLE project_files (
                project_uid TEXT NOT NULL,
                file_uid TEXT NOT NULL,
                uuid TEXT NOT NULL,
                is_active INTEGER NOT NULL
            )
            """
        )
        conn.execute("INSERT INTO project_files VALUES ('p1', 'd1', 'u1', 1)")


def test_rag_ingestion_repository_publishes_only_ready_documents(tmp_path) -> None:
    db_name = str(tmp_path / "rag.sqlite")
    _init_project_binding(db_name)
    init_rag_ingestion_tables(db_name)
    queue_ingestion(
        project_uid="p1",
        doc_uid="d1",
        uuid="u1",
        doc_name="paper.pdf",
        file_path="paper.pdf",
        db_name=db_name,
    )
    save_document_text(
        doc_uid="d1",
        uuid="u1",
        file_path="paper.pdf",
        text_content="paper text",
        text_hash="hash-1",
        db_name=db_name,
    )

    assert list_ready_project_documents(project_uid="p1", uuid="u1", db_name=db_name) == []

    update_ingestion_progress(
        project_uid="p1",
        doc_uid="d1",
        uuid="u1",
        status="ready",
        stage="ready",
        current_items=3,
        total_items=3,
        index_version="settings:hash-1",
        db_name=db_name,
    )
    ready = list_ready_project_documents(project_uid="p1", uuid="u1", db_name=db_name)

    assert ready[0]["doc_uid"] == "d1"
    assert ready[0]["text"] == "paper text"
    assert ready[0]["index_version"] == "settings:hash-1"


def test_ingestion_recovery_only_requeues_lost_local_or_legacy_empty_jobs() -> None:
    def missing(_job_id: str) -> None:
        return None

    assert should_requeue_ingestion(
        {
            "status": "running",
            "queue_job_id": "local-lost",
            "error_message": None,
        },
        get_job_status_fn=missing,
    )
    assert should_requeue_ingestion(
        {
            "status": "failed",
            "queue_job_id": "local-old",
            "error_message": "Document extraction returned empty text",
        },
        get_job_status_fn=missing,
    )
    assert not should_requeue_ingestion(
        {
            "status": "failed",
            "queue_job_id": "local-new",
            "error_message": "RapidOCR 已运行，但没有识别到文本。",
        },
        get_job_status_fn=missing,
    )


def test_ingestion_recovery_requeues_ready_documents_missing_from_lancedb() -> None:
    ingestion = {
        "status": "ready",
        "project_uid": "p1",
        "doc_uid": "d1",
        "index_version": "settings:hash",
    }

    assert should_requeue_ingestion(
        ingestion,
        get_job_status_fn=lambda _job_id: None,
        document_index_exists_fn=lambda **_kwargs: False,
    )
    assert not should_requeue_ingestion(
        ingestion,
        get_job_status_fn=lambda _job_id: None,
        document_index_exists_fn=lambda **_kwargs: True,
    )


def test_enqueue_ingestion_keeps_ready_state_if_local_job_finishes_immediately(
    monkeypatch, tmp_path
) -> None:
    db_name = str(tmp_path / "rag.sqlite")
    _init_project_binding(db_name)
    monkeypatch.setattr(
        "agent.application.rag_ingestion.extract_document_payload",
        lambda _path, user_uuid=None, preview_dir=None, progress_callback=None: {
            "result": 1,
            "text": "extracted paper",
        },
    )

    def _ingest(**kwargs):
        callback = kwargs["progress_callback"]
        callback("chunking", 2, 2)
        callback("embedding", 2, 2)
        callback("publishing", 2, 2)
        return {
            "index_version": "settings:hash",
            "text_hash": "hash",
            "chunk_count": 2,
            "reused": False,
        }

    monkeypatch.setattr(
        "agent.application.rag_ingestion.build_project_document_index_with_settings",
        _ingest,
    )
    monkeypatch.setattr(
        "agent.application.rag_ingestion.publish_document_index",
        lambda **_kwargs: 2,
    )

    def _run_immediately(task, *args):
        task(*args)
        return {"mode": "queued", "job_id": "local-1"}

    enqueue_document_ingestion(
        project_uid="p1",
        doc_uid="d1",
        user_uuid="u1",
        doc_name="paper.pdf",
        file_path="paper.pdf",
        enqueue_background_fn=_run_immediately,
        db_name=db_name,
    )
    status = get_ingestion(project_uid="p1", doc_uid="d1", uuid="u1", db_name=db_name)

    assert status is not None
    assert status["status"] == "ready"
    assert status["stage"] == "ready"
    assert status["queue_job_id"] == "local-1"


def test_reindex_reuses_durable_extracted_text(monkeypatch, tmp_path) -> None:
    db_name = str(tmp_path / "rag.sqlite")
    _init_project_binding(db_name)
    save_document_text(
        doc_uid="d1",
        uuid="u1",
        file_path="paper.pdf",
        text_content="durable extracted text",
        text_hash="old-hash",
        db_name=db_name,
    )
    queue_ingestion(
        project_uid="p1",
        doc_uid="d1",
        uuid="u1",
        doc_name="paper.pdf",
        file_path="paper.pdf",
        db_name=db_name,
    )
    monkeypatch.setattr(
        "agent.application.rag_ingestion.extract_document_payload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected parse")),
    )
    monkeypatch.setattr(
        "agent.application.rag_ingestion.build_project_document_index_with_settings",
        lambda **_kwargs: {
            "index_version": "settings:hash",
            "chunk_count": 1,
            "chunks": ["durable extracted text"],
            "metadatas": [{"start_index": 0}],
            "embeddings": [[1.0, 0.0]],
        },
    )
    monkeypatch.setattr(
        "agent.application.rag_ingestion.publish_document_index",
        lambda **_kwargs: 1,
    )

    from agent.application.rag_ingestion import process_document_ingestion

    process_document_ingestion("p1", "d1", "u1", "paper.pdf", "paper.pdf", db_name)

    status = get_ingestion(project_uid="p1", doc_uid="d1", uuid="u1", db_name=db_name)
    stored = get_document_text(doc_uid="d1", uuid="u1", db_name=db_name)
    assert status is not None and status["status"] == "ready"
    assert stored is not None and stored["text_content"] == "durable extracted text"


def test_forced_reprocessing_refreshes_saved_text_and_locations(monkeypatch, tmp_path) -> None:
    db_name = str(tmp_path / "rag.sqlite")
    _init_project_binding(db_name)
    save_document_text(
        doc_uid="d1",
        uuid="u1",
        file_path="paper.pdf",
        text_content="legacy text",
        text_hash="legacy-hash",
        db_name=db_name,
    )
    queue_ingestion(
        project_uid="p1",
        doc_uid="d1",
        uuid="u1",
        doc_name="paper.pdf",
        file_path="paper.pdf",
        db_name=db_name,
    )
    monkeypatch.setattr(
        "agent.application.rag_ingestion.extract_document_payload",
        lambda *_args, **_kwargs: {
            "text": "fresh text",
            "parser": "paddleocr-v6",
            "source_spans": [{"start": 0, "end": 5, "page_no": 1, "polygon": []}],
        },
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "agent.application.rag_ingestion.build_project_document_index_with_settings",
        lambda **kwargs: captured.update(kwargs) or {
            "index_version": "settings:fresh",
            "chunk_count": 1,
            "chunks": ["fresh text"],
            "metadatas": [{}],
            "embeddings": [[1.0]],
        },
    )
    monkeypatch.setattr("agent.application.rag_ingestion.publish_document_index", lambda **_kwargs: 1)

    from agent.application.rag_ingestion import process_document_ingestion

    process_document_ingestion(
        "p1", "d1", "u1", "paper.pdf", "paper.pdf", db_name, force_extraction=True
    )

    stored = get_document_text(doc_uid="d1", uuid="u1", db_name=db_name)
    assert stored is not None and stored["text_content"] == "fresh text"
    assert captured["source_spans"] == [{"start": 0, "end": 5, "page_no": 1, "polygon": []}]


def test_dynamic_project_service_hot_reloads_published_manifest() -> None:
    documents = [
        {
            "doc_uid": "d1",
            "doc_name": "paper.pdf",
            "text": "version one",
            "index_version": "v1",
        }
    ]
    searches: list[tuple[tuple[str, str], ...]] = []

    def _list_ready(**kwargs):
        scope = set(kwargs["doc_uids"])
        return [item for item in documents if item["doc_uid"] in scope]

    def _search(*, project_uid, ready_versions, **_kwargs):
        assert project_uid == "p1"
        manifest = tuple(ready_versions)
        searches.append(manifest)
        return [
            {
                "doc_uid": "d1",
                "doc_name": "paper.pdf",
                "text": documents[0]["text"],
            }
        ]

    service = DynamicProjectEvidenceService(
        project_uid="p1",
        user_uuid="u1",
        doc_uids=["d1"],
        list_ready_documents_fn=_list_ready,
        search_chunks_fn=_search,
        embed_query_fn=lambda _query: [1.0, 0.0],
    )

    assert service.search("q")["evidences"][0]["text"] == "version one"
    documents[0] = {**documents[0], "text": "version two", "index_version": "v2"}
    assert service.search("q")["evidences"][0]["text"] == "version two"
    assert searches == [(("d1", "v1"),), (("d1", "v2"),)]

    service.update_scope([])
    assert service.search("q")["trace"]["reason"] == "no_ready_documents"


def test_dynamic_project_service_reports_no_candidates_for_missing_index() -> None:
    service = DynamicProjectEvidenceService(
        project_uid="p1",
        user_uuid="u1",
        doc_uids=["d1"],
        list_ready_documents_fn=lambda **_kwargs: [
            {
                "doc_uid": "d1",
                "doc_name": "paper.pdf",
                "text": "paper text",
                "index_version": "v1",
            }
        ],
        search_chunks_fn=lambda **_kwargs: [],
        embed_query_fn=lambda _query: [1.0, 0.0],
    )

    result = service.search("question")

    assert result["evidences"] == []
    assert result["trace"]["reason"] == "no_candidates"


def test_ingestion_reports_real_embedding_batches_and_publishes_atomically(
    monkeypatch, tmp_path
) -> None:
    class _Embeddings:
        def __init__(self, **_kwargs):
            pass

        def embed_documents(self, texts):
            return [[1.0, float(len(text))] for text in texts]

        def embed_query(self, _query):
            return [1.0, 10.0]

    monkeypatch.setattr("langchain_community.embeddings.fastembed.FastEmbedEmbeddings", _Embeddings)
    monkeypatch.setenv("AGENT_PROJECT_INDEX_CACHE_DIR", str(tmp_path / "indexes"))
    monkeypatch.setenv("LOCAL_RAG_CHUNK_SIZE", "12")
    monkeypatch.setenv("LOCAL_RAG_CHUNK_OVERLAP", "0")
    monkeypatch.setenv("LOCAL_RAG_PROJECT_MAX_CHARS", "10")
    monkeypatch.setenv("RAG_INDEX_BATCH_SIZE", "2")
    progress: list[tuple[str, int | None, int | None]] = []
    text = "第一段内容。第二段内容。第三段内容。第四段内容。第五段内容。"

    published = build_project_document_index_with_settings(
        project_uid="p1",
        doc_uid="d1",
        doc_name="paper.pdf",
        document_text=text,
        progress_callback=lambda stage, current, total: progress.append((stage, current, total)),
    )

    embedding_updates = [item for item in progress if item[0] == "embedding"]
    assert published["chunk_count"] > 2
    assert published["indexed_char_count"] == len(text)
    assert published["truncated"] is False
    assert len(embedding_updates) >= 2
    assert embedding_updates[-1][1] == embedding_updates[-1][2]
    assert progress[-1][0] == "embedding"

    assert len(published["chunks"]) == published["chunk_count"]
    assert len(published["embeddings"]) == published["chunk_count"]


def test_failed_ingestion_stores_friendly_error_message(monkeypatch, tmp_path) -> None:
    db_name = str(tmp_path / "rag.sqlite")
    _init_project_binding(db_name)
    init_rag_ingestion_tables(db_name)
    queue_ingestion(
        project_uid="p1",
        doc_uid="d1",
        uuid="u1",
        doc_name="paper.pdf",
        file_path="paper.pdf",
        db_name=db_name,
    )

    def _network_failure(*_args, **_kwargs):
        raise Exception("No available model hosting platforms detected. Please check your network connection.")

    monkeypatch.setattr("agent.application.rag_ingestion.extract_document_payload", _network_failure)

    import pytest

    from agent.application.rag_ingestion import process_document_ingestion

    with pytest.raises(Exception):
        process_document_ingestion("p1", "d1", "u1", "paper.pdf", "paper.pdf", db_name)

    ingestion = get_ingestion(project_uid="p1", doc_uid="d1", uuid="u1", db_name=db_name)
    assert ingestion["status"] == "failed"
    assert ingestion["error_message"] == (
        "OCR 模型尚未下载，且当前无法连接模型服务器。请检查网络连接后点击「重试」。"
    )


def test_friendly_error_message_covers_known_failures() -> None:
    from agent.application.rag_ingestion import (
        _LEGACY_EMPTY_TEXT_ERROR_MESSAGE,
        EMPTY_TEXT_ERROR_MESSAGE,
        _friendly_error_message,
    )

    network = _friendly_error_message(
        Exception("No available model hosting platforms detected. Please check your network connection.")
    )
    assert "模型服务器" in network

    fastembed = _friendly_error_message(
        ImportError("Could not import 'fastembed' Python package. Please install it with `pip install fastembed`.")
    )
    assert "重新安装" in fastembed

    partial_download = _friendly_error_message(
        Exception("NO_SUCHFILE : 3 : Load model model_optimized.onnx failed. File doesn't exist")
    )
    assert "缓存不完整" in partial_download

    assert _friendly_error_message(ValueError(_LEGACY_EMPTY_TEXT_ERROR_MESSAGE)) == EMPTY_TEXT_ERROR_MESSAGE
    assert _friendly_error_message(ValueError("文档没有可识别的页面。")) == "文档没有可识别的页面。"


def test_should_requeue_accepts_localized_empty_text_error() -> None:
    from agent.application.rag_ingestion import EMPTY_TEXT_ERROR_MESSAGE

    localized = {"status": "failed", "error_message": EMPTY_TEXT_ERROR_MESSAGE}
    legacy = {"status": "failed", "error_message": "Document extraction returned empty text"}
    assert should_requeue_ingestion(localized, get_job_status_fn=lambda _job_id: None) is True
    assert should_requeue_ingestion(legacy, get_job_status_fn=lambda _job_id: None) is True
