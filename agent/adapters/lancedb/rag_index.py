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
            pa.field("section_path", pa.string(), nullable=False),
            pa.field("heading_level", pa.int64(), nullable=False),
            pa.field("prev_chunk_id", pa.string()),
            pa.field("next_chunk_id", pa.string()),
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
                "section_path": str(metadata.get("section_path") or ""),
                "heading_level": int(metadata.get("heading_level") or 0),
                "prev_chunk_id": (
                    str(metadata["prev_chunk_id"])
                    if metadata.get("prev_chunk_id")
                    else None
                ),
                "next_chunk_id": (
                    str(metadata["next_chunk_id"])
                    if metadata.get("next_chunk_id")
                    else None
                ),
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
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse separately retrieved dense and FTS/BM25 candidates with RRF.

    Keeping both ranked lists is intentional: the returned score is an RRF
    score, not a provider-specific hybrid score, so retrieval traces remain
    explainable across LanceDB releases.
    """
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
            dense_rows = (
                table.search(query_vector)
                .where(condition, prefilter=True)
                .limit(max(1, limit))
                .to_list()
            )
            sparse_rows = (
                table.search(query, query_type="fts")
                .where(condition, prefilter=True)
                .limit(max(1, limit))
                .to_list()
            )
            candidates.extend(_fuse_rrf(dense_rows, sparse_rows, rrf_k=rrf_k))
    candidates.sort(key=lambda item: float(item["_relevance_score"]), reverse=True)
    return candidates[: max(1, limit)]


def _fuse_rrf(
    dense_rows: list[dict[str, Any]], sparse_rows: list[dict[str, Any]], *, rrf_k: int
) -> list[dict[str, Any]]:
    """Return chunk-id-deduplicated RRF candidates, retaining rank provenance."""
    fused: dict[str, dict[str, Any]] = {}
    denominator = max(1, int(rrf_k))
    for source, rows in (("dense", dense_rows), ("bm25", sparse_rows)):
        for rank, raw_row in enumerate(rows, start=1):
            chunk_id = str(raw_row.get("chunk_id") or "")
            if not chunk_id:
                continue
            row = fused.setdefault(chunk_id, dict(raw_row))
            row["_relevance_score"] = float(row.get("_relevance_score", 0.0)) + 1.0 / (
                denominator + rank
            )
            row[f"_{source}_rank"] = rank
    results: list[dict[str, Any]] = []
    for row in fused.values():
        row.pop("vector", None)
        row.pop("_score", None)
        row.pop("_distance", None)
        results.append(row)
    return results


__all__ = [
    "document_index_exists",
    "publish_document_index",
    "search_published_chunks",
]
