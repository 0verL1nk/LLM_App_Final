import os
from base64 import b64encode
from collections.abc import Callable
from pathlib import Path
from typing import Any

from utils.utils import extract_files

from .llm import create_chat_model
from .user_settings import read_api_key_for_user, read_base_url_for_user, read_model_name_for_user


class DocumentExtractionError(ValueError):
    """Raised when a parser cannot produce searchable document text."""


ExtractionProgressCallback = Callable[[str, int | None, int | None], None]


def _extract_rtf_text(file_path: str) -> str | None:
    from striprtf.striprtf import rtf_to_text

    raw = Path(file_path).read_bytes()
    if not raw.lstrip().startswith(b"{\\rtf"):
        return None
    return rtf_to_text(raw.decode("latin-1"), errors="ignore").strip()


def _extract_scanned_pdf_with_vision_model(
    file_path: str,
    *,
    user_uuid: str,
    progress_callback: ExtractionProgressCallback | None = None,
) -> str:
    import fitz

    api_key = read_api_key_for_user(uuid=user_uuid)
    model_name = read_model_name_for_user(uuid=user_uuid)
    if not api_key or not model_name:
        raise DocumentExtractionError("扫描 PDF OCR 需要先配置支持视觉输入的模型连接。")
    model = create_chat_model(
        api_key=api_key,
        model_name=model_name,
        base_url=read_base_url_for_user(uuid=user_uuid),
        temperature=0,
    )
    scale = max(1.0, float(os.getenv("VISION_OCR_PDF_RENDER_SCALE", "1.25")))
    parts: list[str] = []
    with fitz.open(file_path) as document:
        total_pages = len(document)
        for page_index, page in enumerate(document):
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(scale, scale),
                colorspace=fitz.csRGB,
                alpha=False,
            )
            image_url = "data:image/png;base64," + b64encode(pixmap.tobytes("png")).decode("ascii")
            result = model.invoke([{
                "role": "user",
                "content": [
                    {"type": "text", "text": "请逐字转录这页扫描文档。保留标题、段落、列表和公式；不要解释、概括或补充内容。"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }])
            page_text = str(getattr(result, "content", result) or "").strip()
            if page_text:
                parts.append(f"## Page {page_index + 1}\n\n{page_text}")
            if progress_callback is not None:
                progress_callback("ocr", page_index + 1, total_pages)
    return "\n\n".join(parts)


def extract_document_payload(
    file_path: str,
    *,
    user_uuid: str | None = None,
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
            if not user_uuid:
                raise DocumentExtractionError("扫描 PDF OCR 缺少用户模型配置。")
            try:
                ocr_text = _extract_scanned_pdf_with_vision_model(
                    file_path,
                    user_uuid=user_uuid,
                    progress_callback=progress_callback,
                )
            except Exception as exc:
                raise DocumentExtractionError(f"扫描 PDF 的视觉模型 OCR 解析失败：{exc}") from exc
            if not ocr_text.strip():
                raise DocumentExtractionError("视觉模型 OCR 已运行，但没有识别到文本。")
            return {
                **payload,
                "result": 1,
                "text": ocr_text.strip(),
                "format": "markdown",
                "parser": "vision-ocr",
            }
        raise DocumentExtractionError("文档解析完成，但没有提取到可索引文本。")
    return {**payload, "text": text.strip()}


__all__ = [
    "DocumentExtractionError",
    "ExtractionProgressCallback",
    "extract_document_payload",
]
