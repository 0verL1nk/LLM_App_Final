import logging
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_PAPER_API = "https://api.semanticscholar.org/graph/v1/paper"
SEMANTIC_SCHOLAR_FIELDS = ",".join(
    [
        "paperId",
        "title",
        "authors",
        "year",
        "venue",
        "url",
        "externalIds",
        "isOpenAccess",
        "openAccessPdf",
    ]
)
# Citation responses nest the target paper under "citingPaper"/"citedPaper".
_CITATION_DIRECTION_FIELDS = {"citations": "citingPaper", "references": "citedPaper"}
# Open-access PDF downloads are bounded so one tool call cannot exhaust memory
# or the ingestion pipeline; arXiv papers are typically well under this cap.
MAX_PAPER_PDF_BYTES = 50 * 1024 * 1024


class ScholarlySearchError(RuntimeError):
    pass


def _paper_from_semantic_scholar(item: dict[str, Any]) -> dict[str, Any]:
    authors = item.get("authors") or []
    author_names = [
        author.get("name", "").strip()
        for author in authors
        if isinstance(author, dict) and author.get("name")
    ]
    ext_ids_raw = item.get("externalIds")
    external_ids: dict[str, Any] = ext_ids_raw if isinstance(ext_ids_raw, dict) else {}
    doi = external_ids.get("DOI") if isinstance(external_ids.get("DOI"), str) else None

    open_access_pdf = item.get("openAccessPdf")
    open_access_url = (
        open_access_pdf.get("url")
        if isinstance(open_access_pdf, dict) and isinstance(open_access_pdf.get("url"), str)
        else None
    )
    url = item.get("url") if isinstance(item.get("url"), str) else None
    if not url and open_access_url:
        url = open_access_url
    if not url and doi:
        url = f"https://doi.org/{doi}"

    return {
        "paper_id": item.get("paperId") if isinstance(item.get("paperId"), str) else "",
        "title": item.get("title") if isinstance(item.get("title"), str) else "",
        "authors": author_names,
        "year": item.get("year") if isinstance(item.get("year"), int) else None,
        "venue": item.get("venue") if isinstance(item.get("venue"), str) else "",
        "doi": doi,
        "url": url or "",
        "open_access": bool(item.get("isOpenAccess")),
    }


def search_semantic_scholar(
    query: str,
    limit: int = 5,
    timeout_seconds: float = 8.0,
) -> list[dict[str, Any]]:
    query_normalized = query.strip()
    if not query_normalized:
        return []

    safe_limit = max(1, min(limit, 20))
    params: dict[str, Any] = {
        "query": query_normalized,
        "limit": safe_limit,
        "fields": SEMANTIC_SCHOLAR_FIELDS,
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(SEMANTIC_SCHOLAR_API, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException as exc:
        raise ScholarlySearchError("Semantic Scholar request timed out.") from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        raise ScholarlySearchError(
            f"Semantic Scholar request failed with status {status_code}."
        ) from exc
    except Exception as exc:
        raise ScholarlySearchError(f"Semantic Scholar request failed: {exc}") from exc

    papers_raw = payload.get("data")
    if not isinstance(papers_raw, list):
        logger.warning("Unexpected Semantic Scholar payload: missing 'data' list.")
        return []

    parsed = [_paper_from_semantic_scholar(item) for item in papers_raw if isinstance(item, dict)]
    return [paper for paper in parsed if paper.get("title")]


def fetch_semantic_scholar_citations(
    paper_id: str,
    *,
    direction: Literal["citations", "references"] = "citations",
    limit: int = 10,
    timeout_seconds: float = 8.0,
) -> list[dict[str, Any]]:
    """Fetch one hop of the Semantic Scholar citation graph for snowballing."""
    normalized_id = paper_id.strip()
    if not normalized_id:
        return []
    safe_limit = max(1, min(limit, 50))
    endpoint = f"{SEMANTIC_SCHOLAR_PAPER_API}/{normalized_id}/{direction}"
    paper_field = _CITATION_DIRECTION_FIELDS[direction]
    params: dict[str, Any] = {
        "limit": safe_limit,
        "fields": f"{paper_field}.{SEMANTIC_SCHOLAR_FIELDS}",
    }
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException as exc:
        raise ScholarlySearchError("Semantic Scholar citation request timed out.") from exc
    except httpx.HTTPStatusError as exc:
        raise ScholarlySearchError(
            f"Semantic Scholar citation request failed with status {exc.response.status_code}."
        ) from exc
    except Exception as exc:
        raise ScholarlySearchError(f"Semantic Scholar citation request failed: {exc}") from exc

    rows = payload.get("data")
    if not isinstance(rows, list):
        logger.warning("Unexpected Semantic Scholar citation payload: missing 'data' list.")
        return []
    parsed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        paper = row.get(paper_field)
        if isinstance(paper, dict):
            parsed.append(_paper_from_semantic_scholar(paper))
    return [paper for paper in parsed if paper.get("title")]


def download_paper_pdf(url: str, *, timeout_seconds: float = 30.0) -> bytes:
    """Download one open-access paper PDF with size and format guards."""
    normalized_url = url.strip()
    if not normalized_url.startswith(("https://", "http://")):
        raise ScholarlySearchError("Paper download URL must be an http(s) link.")
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            with client.stream("GET", normalized_url) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_PAPER_PDF_BYTES:
                        raise ScholarlySearchError(
                            "Paper download exceeded the 50 MB limit."
                        )
                    chunks.append(chunk)
    except httpx.TimeoutException as exc:
        raise ScholarlySearchError("Paper download timed out.") from exc
    except httpx.HTTPStatusError as exc:
        raise ScholarlySearchError(
            f"Paper download failed with status {exc.response.status_code}."
        ) from exc
    except ScholarlySearchError:
        raise
    except Exception as exc:
        raise ScholarlySearchError(f"Paper download failed: {exc}") from exc

    content = b"".join(chunks)
    if not content.startswith(b"%PDF"):
        raise ScholarlySearchError("Downloaded content is not a PDF (missing %PDF header).")
    return content


def format_search_papers_results(papers: list[dict[str, Any]]) -> str:
    if not papers:
        return "No academic papers found for this query."

    lines: list[str] = []
    for index, paper in enumerate(papers, start=1):
        title = paper.get("title") or "Untitled"
        year = paper.get("year")
        year_text = str(year) if isinstance(year, int) else "n/a"
        authors = paper.get("authors") or []
        if isinstance(authors, list) and authors:
            author_text = ", ".join(str(name) for name in authors[:4])
            if len(authors) > 4:
                author_text += ", et al."
        else:
            author_text = "n/a"
        venue = paper.get("venue") or "n/a"
        doi = paper.get("doi") or "n/a"
        url = paper.get("url") or "n/a"
        open_access = "yes" if paper.get("open_access") else "no"

        lines.append(f"{index}. {title} ({year_text})")
        lines.append(f"   Authors: {author_text}")
        lines.append(f"   Venue: {venue}")
        lines.append(f"   DOI: {doi}")
        lines.append(f"   URL: {url}")
        lines.append(f"   Open Access: {open_access}")
        paper_id = paper.get("paper_id") or ""
        if paper_id:
            lines.append(f"   PaperId: {paper_id}")

    return "\n".join(lines)
