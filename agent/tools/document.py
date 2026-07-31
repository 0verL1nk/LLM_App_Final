"""文档工具模块"""

import json
import logging
from collections.abc import Callable
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from .utils import _is_dangerous_query, _preview, _sanitize_query

logger = logging.getLogger(__name__)


class SearchDocumentInput(BaseModel):
    query: str = Field(
        description="Specific paper question or keyword used to retrieve evidence snippets."
    )


class ListDocumentInput(BaseModel):
    verbose: bool = Field(
        default=False,
        description="If True, include character length for each document.",
    )


class ReadDocumentInput(BaseModel):
    doc_id: str = Field(
        default="",
        description="Document identifier to read. Use doc_id from list_document output. If empty, reads the only available document.",
    )
    offset: int = Field(
        default=0,
        description="Character offset to start reading from (0 means start from beginning).",
    )
    limit: int = Field(
        default=2000,
        description="Maximum number of characters to read (recommended 1000-3000 for context).",
    )
    include_rag: bool = Field(
        default=False,
        description="Whether to use RAG to retrieve relevant context around the reading position.",
    )


def build_search_document_tool(
    search_document_fn: Callable[[str], str],
    search_document_evidence_fn: Callable[[str], dict[str, Any]] | None = None,
) -> Any:
    """构建文档搜索工具"""
    @tool(
        "search_document",
        description="""Search uploaded paper content for relevant evidence snippets using RAG.

Returns: JSON object with structure:
{
  "evidences": [
    {
      "chunk_id": "unique_chunk_identifier",
      "text": "evidence text content",
      "score": 0.95,
      "page_no": 5,
      "offset_start": 100,
      "offset_end": 200,
      "doc_name": "document.pdf"
    }
  ]
}

IMPORTANT: When citing evidence in your answer, use the format:
<evidence>chunk_id|p{page_no}|o{offset_start}-{offset_end}</evidence>

Example: Based on the research<evidence>chunk_abc123|p5|o100-200</evidence>, the method is effective.""",
        args_schema=SearchDocumentInput,
    )
    def search_document(query: str) -> str:
        safe_query = _sanitize_query(query)
        logger.info(
            "tool.search_document called: query_len=%s query_preview=%s",
            len(safe_query),
            _preview(safe_query),
        )
        if not safe_query:
            logger.warning("tool.search_document blocked: empty query after sanitization")
            return "Document search query is empty after sanitization."
        if _is_dangerous_query(safe_query):
            logger.warning("tool.search_document blocked by policy")
            return "Blocked by tool policy: query appears unsafe for document search."
        if search_document_evidence_fn is not None:
            try:
                evidence_payload = search_document_evidence_fn(safe_query)
                evidence_count = (
                    len(evidence_payload.get("evidences", []))
                    if isinstance(evidence_payload, dict)
                    else 0
                )
                logger.info(
                    "tool.search_document success: mode=evidence_json evidences=%s",
                    evidence_count,
                )
                return json.dumps(evidence_payload, ensure_ascii=False)
            except Exception:
                logger.exception("tool.search_document evidence function failed, fallback=text")
                return search_document_fn(safe_query)
        logger.info("tool.search_document success: mode=text")
        return search_document_fn(safe_query)

    return search_document


def build_list_document_tool(
    list_documents_fn: Callable[[], list[dict[str, Any]]],
) -> Any:
    """构建文档列表工具"""

    @tool(
        "list_document",
        description="List all documents loaded in the current project scope with their names and identifiers.",
        args_schema=ListDocumentInput,
    )
    def list_document(verbose: bool = False) -> str:
        logger.info("tool.list_document called: verbose=%s", verbose)
        try:
            docs = list_documents_fn()
        except Exception as exc:
            logger.exception("tool.list_document failed: %s", exc)
            return f"Failed to list documents: {exc}"
        if not isinstance(docs, list) or not docs:
            logger.info("tool.list_document: no documents found")
            return "No documents loaded in current project scope."
        items: list[dict[str, Any]] = []
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            entry: dict[str, Any] = {
                "doc_uid": str(doc.get("doc_uid") or doc.get("uid") or ""),
                "doc_name": str(doc.get("doc_name") or doc.get("file_name") or ""),
            }
            if verbose:
                char_length = doc.get("char_length")
                entry["char_length"] = (
                    int(char_length)
                    if isinstance(char_length, int)
                    else len(str(doc.get("text") or ""))
                )
            items.append(entry)
        logger.info("tool.list_document success: count=%s", len(items))
        return json.dumps({"count": len(items), "documents": items}, ensure_ascii=False)

    return list_document


def build_read_document_tool(
    read_document_fn: Callable[[int, int], tuple[str, int]] | None,
    search_document_fn: Callable[[str], str],
    doc_id_to_text: dict[str, str] | None = None,
    default_doc_id: str = "",
    read_document_by_id_fn: Callable[[str, int, int], tuple[str, int]] | None = None,
) -> Any:
    """构建文档阅读工具

    Args:
        read_document_fn: 单文档读取函数，接收 (offset, limit)，返回 (content, total_len)
        search_document_fn: RAG 检索函数
        doc_id_to_text: 多文档映射表 {doc_id: document_text}，非空时启用多文档模式
        default_doc_id: 默认文档 ID（多文档模式下且 doc_id 为空时使用）
    """

    @tool(
        "read_document",
        description="Read a specific portion of a document by character offset and limit. "
        "Use doc_id to select which document (from list_document output). "
        "Use offset to skip to a position, limit to control chunk size. "
        "Set include_rag=True to get relevant context around the reading position. "
        "Returns JSON with a citeable evidence span; use its citation field for every claim derived from the span.",
        args_schema=ReadDocumentInput,
    )
    def read_document(
        doc_id: str = "", offset: int = 0, limit: int = 2000, include_rag: bool = False
    ) -> str:
        logger.info(
            "tool.read_document called: doc_id=%s offset=%s limit=%s include_rag=%s",
            doc_id,
            offset,
            limit,
            include_rag,
        )

        if callable(read_document_by_id_fn):
            content, total = read_document_by_id_fn(doc_id, offset, limit)
            doc_label = doc_id.strip() or "文档"
            if total <= 0:
                return (
                    f"Document '{doc_id}' is not ready or not available in the current scope. "
                    "Use list_document to inspect ready documents."
                )
        # 多文档模式
        elif doc_id_to_text is not None:
            target_doc_id = doc_id.strip() or default_doc_id
            if not target_doc_id:
                available = list(doc_id_to_text.keys())
                if len(available) == 1:
                    target_doc_id = available[0]
                else:
                    return (
                        "read_document requires doc_id when multiple documents are in scope. "
                        "Use list_document(verbose=True) to see available doc_ids. "
                        f"Available: {available}"
                    )
            if target_doc_id not in doc_id_to_text:
                return f"Document '{target_doc_id}' not found. Use list_document(verbose=True) to see available doc_ids."
            text = doc_id_to_text[target_doc_id]
            total = len(text)
            content = text[offset : offset + limit]
            doc_label = target_doc_id
        else:
            # 单文档模式（向后兼容）
            if callable(read_document_fn):
                content, total = read_document_fn(offset, limit)
            else:
                content, total = "", 0
            doc_label = "文档"

        rag_context = ""
        if include_rag:
            query = f"position_{offset}"
            rag_context = search_document_fn(query)

        safe_offset = max(0, int(offset))
        offset_end = safe_offset + len(content)
        chunk_id = f"{doc_label}:offset_{safe_offset}_{offset_end}"
        citation = f"{chunk_id}|pnull|o{safe_offset}-{offset_end}"
        result = json.dumps(
            {
                "evidences": [
                    {
                        "chunk_id": chunk_id,
                        "doc_uid": doc_label,
                        "text": content,
                        "page_no": None,
                        "offset_start": safe_offset,
                        "offset_end": offset_end,
                        "citation": citation,
                    }
                ],
                "related_context": rag_context,
                "trace": {
                    "mode": "sequential_read",
                    "total_chars": total,
                    "returned_chars": len(content),
                },
            },
            ensure_ascii=False,
        )
        logger.info(
            "tool.read_document success: doc_id=%s chunk_len=%s total_len=%s",
            doc_id or "default",
            len(content),
            total,
        )
        return result

    return read_document
