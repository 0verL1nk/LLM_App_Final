"""Versioned LanceDB storage for project RAG chunks."""

import hashlib
import json
import os
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa
from lancedb.index import FTS

_LOCK = threading.RLock()
_TABLE_PREFIX = "rag_chunks"


def _database_path() -> Path:
    return Path(os.getenv("AGENT_LANCEDB_DIR", "./.cache/lancedb"))


def _table_name(settings_signature: str, vector_size: int) -> str:
    safe_signature = "".join(ch for ch in settings_signature.lower() if ch.isalnum())[:24]
    if not safe_signature:
        raise ValueError("LanceDB index requires a settings signature")
    return f"{_TABLE_PREFIX}_{safe_signature}_{vector_size}"


def _schema(vector_size: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("chunk_id", pa.string(), nullable=False),
            pa.field("project_uid", pa.string(), nullable=False),
            pa.field("doc_uid", pa.string(), nullable=False),
            pa.field("doc_name", pa.string(), nullable=False),
            pa.field("index_version", pa.string(), nullable=False),
            pa.field("chunk_index", pa.int64(), nullable=False),
            pa.field("start_index", pa.int64()),
            pa.field("page_no", pa.int64()),
            pa.field("ocr_locations_json", pa.string()),
            pa.field("text", pa.string(), nullable=False),
            pa.field("vector", pa.list_(pa.float32(), vector_size), nullable=False),
        ]
    )


def _connect() -> Any:
    path = _database_path()
    path.mkdir(parents=True, exist_ok=True)
    return lancedb.connect(path)


def _table_names(database: Any) -> set[str]:
    return set(database.list_tables().tables)


def _open_or_create_table(*, settings_signature: str, vector_size: int) -> Any:
    database = _connect()
    name = _table_name(settings_signature, vector_size)
    if name in _table_names(database):
        return database.open_table(name)
    return database.create_table(name, schema=_schema(vector_size))


def _sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _version_filter(project_uid: str, versions: list[tuple[str, str]]) -> str:
    version_clauses = [
        f"(doc_uid = {_sql_literal(doc_uid)} AND index_version = {_sql_literal(version)})"
        for doc_uid, version in versions
    ]
    if not version_clauses:
        raise ValueError("At least one ready document version is required")
    return f"project_uid = {_sql_literal(project_uid)} AND (" + " OR ".join(version_clauses) + ")"


def document_index_exists(
    *,
    project_uid: str,
    doc_uid: str,
    index_version: str,
    vector_size: int | None = None,
) -> bool:
    settings_signature = index_version.split(":", 1)[0]
    with _LOCK:
        database = _connect()
        table_names = _table_names(database)
        safe_signature = "".join(ch for ch in settings_signature.lower() if ch.isalnum())[:24]
        names = (
            [_table_name(settings_signature, vector_size)]
            if isinstance(vector_size, int)
            else [
                name
                for name in table_names
                if name.startswith(f"{_TABLE_PREFIX}_{safe_signature}_")
            ]
        )
        condition = _version_filter(project_uid, [(doc_uid, index_version)])
        return any(
            database.open_table(name).count_rows(condition) > 0
            for name in names
            if name in table_names
        )


def publish_document_index(
    *,
    project_uid: str,
    doc_uid: str,
    doc_name: str,
    index_version: str,
    chunks: list[str],
    metadatas: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> int:
    """Publish versioned rows; SQLite ready state controls external visibility."""
    if not chunks or len(chunks) != len(metadatas) or len(chunks) != len(embeddings):
        raise ValueError("LanceDB publish requires aligned non-empty chunks and vectors")
    vector_size = len(embeddings[0])
    if vector_size <= 0 or any(len(vector) != vector_size for vector in embeddings):
        raise ValueError("LanceDB publish requires consistent embedding dimensions")
    settings_signature = index_version.split(":", 1)[0]
    rows: list[dict[str, Any]] = []
    for chunk_index, (text, metadata, vector) in enumerate(
        zip(chunks, metadatas, embeddings, strict=True)
    ):
        identity = f"{project_uid}\0{doc_uid}\0{index_version}\0{chunk_index}"
        rows.append(
            {
                "chunk_id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                "project_uid": project_uid,
                "doc_uid": doc_uid,
                "doc_name": doc_name,
                "index_version": index_version,
                "chunk_index": chunk_index,
                "start_index": (
                    metadata.get("start_index")
                    if isinstance(metadata.get("start_index"), int)
                    else None
                ),
                "page_no": (
                    metadata.get("page_no")
                    if isinstance(metadata.get("page_no"), int)
                    else None
                ),
                "ocr_locations_json": json.dumps(
                    metadata.get("ocr_locations", []),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "text": text,
                "vector": [float(value) for value in vector],
            }
        )

    with _LOCK:
        table = _open_or_create_table(
            settings_signature=settings_signature,
            vector_size=vector_size,
        )
        condition = _version_filter(project_uid, [(doc_uid, index_version)])
        table.delete(condition)
        table.add(pa.Table.from_pylist(rows, schema=_schema(vector_size)))
        table.create_index(
            "text",
            replace=True,
            config=FTS(
                base_tokenizer="ngram",
                ngram_min_length=2,
                ngram_max_length=3,
                lower_case=True,
                stem=False,
                remove_stop_words=False,
                ascii_folding=False,
            ),
        )
        min_rows = max(256, int(os.getenv("LANCEDB_VECTOR_INDEX_MIN_ROWS", "1000")))
        if table.count_rows() >= min_rows:
            table.create_index(
                metric="cosine",
                vector_column_name="vector",
                index_type="IVF_HNSW_SQ",
                replace=True,
            )
    return len(rows)


def search_published_chunks(
    *,
    project_uid: str,
    ready_versions: list[tuple[str, str]],
    query: str,
    query_vector: list[float],
    limit: int,
) -> list[dict[str, Any]]:
    """Run LanceDB native dense + BM25 hybrid search over ready versions only."""
    if not ready_versions or not query_vector:
        return []
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for doc_uid, index_version in ready_versions:
        grouped[index_version.split(":", 1)[0]].append((doc_uid, index_version))

    candidates: list[dict[str, Any]] = []
    with _LOCK:
        database = _connect()
        for signature, versions in grouped.items():
            name = _table_name(signature, len(query_vector))
            if name not in _table_names(database):
                continue
            table = database.open_table(name)
            condition = _version_filter(project_uid, versions)
            rows = (
                table.search(query_type="hybrid")
                .vector(query_vector)
                .text(query)
                .where(condition, prefilter=True)
                .limit(max(1, limit))
                .to_list()
            )
            for row in rows:
                row.pop("vector", None)
                row.pop("_score", None)
                row.pop("_distance", None)
            candidates.extend(rows)
    candidates.sort(
        key=lambda item: float(item.get("_relevance_score", 0.0) or 0.0),
        reverse=True,
    )
    return candidates[: max(1, limit)]


__all__ = [
    "document_index_exists",
    "publish_document_index",
    "search_published_chunks",
]
