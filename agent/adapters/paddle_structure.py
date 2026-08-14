"""Model-driven cross-page reconstruction with PaddleOCR-VL."""

from collections.abc import Callable
from typing import Any


def reconstruct_cross_page_document(
    page_results: list[Any],
    *,
    pipeline: Any,
) -> list[Any]:
    """Merge page results through PaddleOCR-VL's semantic reconstruction API."""
    return list(
        pipeline.restructure_pages(
            page_results,
            merge_tables=True,
            relevel_titles=True,
            concatenate_pages=False,
        )
    )


def create_cross_page_pipeline(*, device: str) -> Any:
    """Create the official document VLM pipeline for capable hardware."""
    from paddleocr import PaddleOCRVL

    return PaddleOCRVL(
        pipeline_version="v1.6",
        device=device,
        use_doc_orientation_classify=True,
        use_doc_unwarping=False,
        use_layout_detection=True,
        use_queues=True,
    )


CrossPagePipelineFactory = Callable[..., Any]


__all__ = [
    "CrossPagePipelineFactory",
    "create_cross_page_pipeline",
    "reconstruct_cross_page_document",
]
