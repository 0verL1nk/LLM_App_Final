import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from utils.utils import extract_files


class DocumentExtractionError(ValueError):
    """Raised when a parser cannot produce searchable document text."""


ExtractionProgressCallback = Callable[[str, int | None, int | None], None]


def _extract_rtf_text(file_path: str) -> str | None:
    from striprtf.striprtf import rtf_to_text

    raw = Path(file_path).read_bytes()
    if not raw.lstrip().startswith(b"{\\rtf"):
        return None
    return rtf_to_text(raw.decode("latin-1"), errors="ignore").strip()


def _extract_scanned_pdf_with_rapidocr(
    file_path: str,
    *,
    progress_callback: ExtractionProgressCallback | None = None,
) -> str:
    import fitz
    import numpy as np
    from rapidocr import RapidOCR

    scale = max(1.0, float(os.getenv("RAPIDOCR_PDF_RENDER_SCALE", "1.5")))
    engine = RapidOCR()
    parts: list[str] = []
    with fitz.open(file_path) as document:
        total_pages = len(document)
        for page_index, page in enumerate(document):
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(scale, scale),
                colorspace=fitz.csRGB,
                alpha=False,
            )
            image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                pixmap.height,
                pixmap.width,
                pixmap.n,
            )
            result = engine(image)
            page_text = "\n".join(
                str(item).strip()
                for item in (getattr(result, "txts", None) or ())
                if str(item).strip()
            )
            if page_text:
                parts.append(f"## Page {page_index + 1}\n\n{page_text}")
            if progress_callback is not None:
                progress_callback("ocr", page_index + 1, total_pages)
    return "\n\n".join(parts)


def extract_document_payload(
    file_path: str,
    *,
    progress_callback: ExtractionProgressCallback | None = None,
) -> dict[str, Any]:
    rtf_text = _extract_rtf_text(file_path)
    if rtf_text is not None:
        if not rtf_text:
            raise DocumentExtractionError("RTF 文档解析完成，但没有提取到正文。")
        return {
            "result": 1,
            "text": rtf_text,
            "format": "plain",
            "parser": "striprtf",
        }
    payload = extract_files(file_path)
    if payload.get("result") != 1:
        detail = str(payload.get("text") or "文档解析器未返回错误详情")
        raise DocumentExtractionError(f"文档解析失败：{detail}")
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        if Path(file_path).suffix.lower() == ".pdf":
            try:
                ocr_text = _extract_scanned_pdf_with_rapidocr(
                    file_path,
                    progress_callback=progress_callback,
                )
            except Exception as exc:
                raise DocumentExtractionError(f"扫描 PDF 的本地 RapidOCR 解析失败：{exc}") from exc
            if not ocr_text.strip():
                raise DocumentExtractionError("RapidOCR 已运行，但没有识别到文本。")
            return {
                **payload,
                "result": 1,
                "text": ocr_text.strip(),
                "format": "markdown",
                "parser": "rapidocr-small",
            }
        raise DocumentExtractionError("文档解析完成，但没有提取到可索引文本。")
    return {**payload, "text": text.strip()}


__all__ = [
    "DocumentExtractionError",
    "ExtractionProgressCallback",
    "extract_document_payload",
]
