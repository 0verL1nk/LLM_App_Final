"""Rendered-document OCR with PaddleOCR and location-preserving output."""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paddle_structure import create_cross_page_pipeline, reconstruct_cross_page_document

logger = logging.getLogger(__name__)


class PaddleOcrError(RuntimeError):
    """Raised when a document cannot be rendered or recognized locally."""


@dataclass(frozen=True)
class OcrProfile:
    """A hardware-compatible PP-OCRv6 model pair."""

    name: str
    detection_model: str
    recognition_model: str
    device: str


def select_ocr_profile() -> OcrProfile:
    """Choose a local PP-OCRv6 tier from actual runtime capabilities."""
    try:
        import onnxruntime

        providers = set(onnxruntime.get_available_providers())
    except Exception:
        providers = set()
    try:
        import psutil

        memory_gib = psutil.virtual_memory().total / 1024**3
    except Exception:
        memory_gib = 0.0
    cpu_count = os.cpu_count() or 1
    if "CUDAExecutionProvider" in providers:
        return OcrProfile(
            name="high_accuracy",
            detection_model="PP-OCRv6_medium_det",
            recognition_model="PP-OCRv6_medium_rec",
            device="gpu:0",
        )
    if memory_gib >= 8 and cpu_count >= 4:
        return OcrProfile(
            name="balanced",
            detection_model="PP-OCRv6_small_det",
            recognition_model="PP-OCRv6_small_rec",
            device="cpu",
        )
    return OcrProfile(
        name="lightweight",
        detection_model="PP-OCRv6_tiny_det",
        recognition_model="PP-OCRv6_tiny_rec",
        device="cpu",
    )


def _cache_dir() -> Path:
    configured = os.getenv("AGENT_OCR_CACHE_DIR", "").strip()
    if configured:
        return Path(configured)
    app_data = os.getenv("AGENT_APP_DATA_DIR", "").strip()
    return Path(app_data) / "models" / "paddleocr" if app_data else Path(".cache/paddleocr")


def _configure_paddlex_cache() -> None:
    cache_dir = _cache_dir().resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(cache_dir))


def _render_pdf_pages(file_path: Path, output_dir: Path) -> list[Path]:
    import fitz

    scale = max(1.0, float(os.getenv("PADDLE_OCR_PDF_RENDER_SCALE", "1.5")))
    pages: list[Path] = []
    with fitz.open(file_path) as document:
        for page_index, page in enumerate(document):
            output_path = output_dir / f"page-{page_index + 1:05d}.png"
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(scale, scale),
                colorspace=fitz.csRGB,
                alpha=False,
            )
            pixmap.save(output_path)
            pages.append(output_path)
    if not pages:
        raise PaddleOcrError("文档没有可识别的页面。")
    return pages


def _find_soffice() -> str | None:
    configured = os.getenv("LIBREOFFICE_BIN", "").strip()
    if configured and Path(configured).is_file():
        return configured
    return shutil.which("soffice") or shutil.which("libreoffice")


def _convert_office_to_pdf(file_path: Path, output_dir: Path) -> Path:
    soffice = _find_soffice()
    if not soffice:
        raise PaddleOcrError(
            "识别 Word、Excel 或 PowerPoint 前需要 LibreOffice。请安装 LibreOffice，"
            "或通过 LIBREOFFICE_BIN 指定 soffice 可执行文件。"
        )
    completed = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(file_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    pdf_path = output_dir / f"{file_path.stem}.pdf"
    if completed.returncode != 0 or not pdf_path.is_file():
        detail = (completed.stderr or completed.stdout or "未知转换错误").strip()
        raise PaddleOcrError(f"LibreOffice 无法将文档渲染为 PDF：{detail}")
    return pdf_path


def _render_document_pages(file_path: str, output_dir: Path) -> list[Path]:
    source = Path(file_path)
    if not source.is_file():
        raise PaddleOcrError("找不到待识别文件。")
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        return _render_pdf_pages(source, output_dir)
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        return [source]
    pdf_path = _convert_office_to_pdf(source, output_dir)
    return _render_pdf_pages(pdf_path, output_dir)


def _result_mapping(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    json_value = getattr(result, "json", None)
    if callable(json_value):
        json_value = json_value()
    if isinstance(json_value, dict):
        return json_value
    if isinstance(json_value, str):
        parsed = json.loads(json_value)
        if isinstance(parsed, dict):
            return parsed
    to_dict = getattr(result, "to_dict", None)
    if callable(to_dict):
        parsed = to_dict()
        if isinstance(parsed, dict):
            return parsed
    raise PaddleOcrError("PaddleOCR 返回了无法读取的识别结果。")


def _polygon(value: Any) -> list[list[float]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list):
        return []
    points: list[list[float]] = []
    for point in value:
        if hasattr(point, "tolist"):
            point = point.tolist()
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            points.append([float(point[0]), float(point[1])])
    return points


def _new_pipeline(profile: OcrProfile) -> Any:
    _configure_paddlex_cache()
    from paddleocr import PaddleOCR

    return PaddleOCR(
        text_detection_model_name=profile.detection_model,
        text_recognition_model_name=profile.recognition_model,
        use_doc_orientation_classify=True,
        use_doc_unwarping=False,
        use_textline_orientation=True,
        device=profile.device,
        engine="onnxruntime",
    )


def _can_use_cross_page_vl(profile: OcrProfile) -> bool:
    """Require Paddle GPU support; ONNX CUDA alone cannot run PaddleOCR-VL."""
    if not profile.device.startswith("gpu:"):
        return False
    try:
        import paddle

        return bool(paddle.is_compiled_with_cuda())
    except (ImportError, AttributeError):
        return False


def _markdown_text(result: Any) -> str:
    markdown = getattr(result, "markdown", None)
    if isinstance(markdown, dict):
        value = markdown.get("markdown_texts", "")
        return value if isinstance(value, str) else ""
    return ""


def _structured_payload(result: Any) -> dict[str, Any]:
    """Unwrap a PaddleOCR-VL page result without depending on a result class."""
    payload = _result_mapping(result)
    nested = payload.get("res")
    return nested if isinstance(nested, dict) else payload


def _structured_polygon(value: Any) -> list[list[float]]:
    """Turn a layout bounding box or polygon into the shared polygon shape."""
    polygon = _polygon(value)
    if polygon:
        return polygon
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        left, top, right, bottom = (float(item) for item in value[:4])
        return [[left, top], [right, top], [right, bottom], [left, bottom]]
    return []


def _structured_source_spans(results: list[Any], text: str) -> list[dict[str, Any]]:
    """Map VL layout blocks back to its generated Markdown text and page geometry."""
    spans: list[dict[str, Any]] = []
    cursor = 0
    for fallback_page_no, result in enumerate(results, start=1):
        payload = _structured_payload(result)
        raw_page_no = payload.get("page_index", fallback_page_no - 1)
        page_no = int(raw_page_no) + 1 if isinstance(raw_page_no, int) else fallback_page_no
        blocks = payload.get("parsing_res_list") or []
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            content = str(block.get("block_content") or "").strip()
            if not content:
                continue
            start = text.find(content, cursor)
            if start < 0:
                # A table or title can move while the VLM repairs page flow;
                # retain only locations whose text is present in the final output.
                continue
            end = start + len(content)
            spans.append(
                {
                    "start": start,
                    "end": end,
                    "page_no": page_no,
                    "polygon": _structured_polygon(block.get("block_bbox") or block.get("block_polygon")),
                    "confidence": None,
                }
            )
            cursor = end
    return spans


PipelineFactory = Callable[[OcrProfile], Any]


def extract_document_with_paddle_ocr(
    file_path: str,
    *,
    progress_callback: Callable[[str, int | None, int | None], None] | None = None,
    pipeline_factory: PipelineFactory = _new_pipeline,
) -> dict[str, Any]:
    """Render a document, OCR every page, and preserve text-to-geometry spans."""
    profile = select_ocr_profile()
    if progress_callback is not None:
        progress_callback("loading_model", None, None)
    with tempfile.TemporaryDirectory(prefix="papersage-ocr-") as temporary_dir:
        pages = _render_document_pages(file_path, Path(temporary_dir))
        if len(pages) > 1 and _can_use_cross_page_vl(profile):
            try:
                structured_pipeline = create_cross_page_pipeline(device=profile.device)
                page_results = list(structured_pipeline.predict([str(page) for page in pages]))
                merged_results = reconstruct_cross_page_document(page_results, pipeline=structured_pipeline)
                merged_text = "\n\n".join(filter(None, (_markdown_text(result) for result in merged_results))).strip()
                if merged_text:
                    return {
                        "text": merged_text,
                        "parser": "paddleocr-vl-cross-page",
                        "ocr_profile": profile.name,
                        "source_spans": _structured_source_spans(merged_results, merged_text),
                    }
            except Exception:
                # The normal OCR pipeline remains the stable fallback when the
                # optional VLM cannot be initialized on a given machine.
                logger.exception("Cross-page PaddleOCR-VL reconstruction failed; falling back to OCR")
        pipeline = pipeline_factory(profile)
        page_texts: list[str] = []
        spans: list[dict[str, Any]] = []
        offset = 0
        for page_no, image_path in enumerate(pages, start=1):
            if page_texts:
                offset += 2
            results = list(pipeline.predict(str(image_path)))
            if not results:
                continue
            payload = _result_mapping(results[0])
            texts = payload.get("rec_texts") or []
            scores = payload.get("rec_scores") or []
            polygons = payload.get("rec_polys") or payload.get("dt_polys") or []
            page_parts: list[str] = []
            for index, raw_text in enumerate(texts):
                text = str(raw_text or "").strip()
                if not text:
                    continue
                if page_parts:
                    page_parts.append("\n")
                    offset += 1
                start = offset
                page_parts.append(text)
                offset += len(text)
                score = scores[index] if index < len(scores) else None
                spans.append(
                    {
                        "start": start,
                        "end": offset,
                        "page_no": page_no,
                        "polygon": _polygon(polygons[index]) if index < len(polygons) else [],
                        "confidence": float(score) if isinstance(score, (int, float)) else None,
                    }
                )
            page_text = "".join(page_parts).strip()
            if page_text:
                page_texts.append(page_text)
            if progress_callback is not None:
                progress_callback("ocr", page_no, len(pages))
    text = "\n\n".join(page_texts).strip()
    if not text:
        raise PaddleOcrError("PaddleOCR 已运行，但没有识别到可索引文本。")
    return {
        "text": text,
        "parser": "paddleocr-v6",
        "ocr_profile": profile.name,
        "source_spans": spans,
    }


__all__ = [
    "OcrProfile",
    "PaddleOcrError",
    "extract_document_with_paddle_ocr",
    "select_ocr_profile",
]
