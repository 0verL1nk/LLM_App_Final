"""Document extraction adapter backed by rendered-page PaddleOCR."""

from collections.abc import Callable
from typing import Any

from .paddle_ocr import PaddleOcrError, extract_document_with_paddle_ocr


class DocumentExtractionError(ValueError):
    """Raised when a parser cannot produce searchable document text."""


ExtractionProgressCallback = Callable[[str, int | None, int | None], None]


def extract_document_payload(
    file_path: str,
    *,
    user_uuid: str | None = None,
    preview_dir: str | None = None,
    progress_callback: ExtractionProgressCallback | None = None,
) -> dict[str, Any]:
    """Extract every supported document through a rendered PaddleOCR pipeline."""
    del user_uuid  # OCR is local and no longer requires a user model connection.
    try:
        payload = extract_document_with_paddle_ocr(
            file_path,
            preview_dir=preview_dir,
            progress_callback=progress_callback,
        )
    except PaddleOcrError as exc:
        raise DocumentExtractionError(str(exc)) from exc
    return {
        "result": 1,
        "text": str(payload["text"]),
        "format": str(payload.get("format") or "plain"),
        "parser": str(payload["parser"]),
        "ocr_profile": str(payload["ocr_profile"]),
        "source_spans": list(payload.get("source_spans") or []),
        "preview_pages": list(payload.get("preview_pages") or []),
    }


__all__ = [
    "DocumentExtractionError",
    "ExtractionProgressCallback",
    "extract_document_payload",
]
