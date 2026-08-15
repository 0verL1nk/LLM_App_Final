"""Runtime OCR tier selection and the shared PaddleX model cache location."""

import os
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..settings import load_agent_settings


@dataclass(frozen=True)
class OcrProfile:
    """A hardware-compatible PP-OCRv6 model pair."""

    name: str
    detection_model: str
    recognition_model: str
    device: str


@lru_cache(maxsize=1)
def _cuda_runtime_usable() -> bool:
    """Guard against onnxruntime-gpu builds, which always list
    CUDAExecutionProvider even when no NVIDIA driver is installed."""
    return shutil.which("nvidia-smi") is not None


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
    if "CUDAExecutionProvider" in providers and _cuda_runtime_usable():
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


def ocr_runtime_capability() -> dict[str, Any]:
    """Report the OCR tier this runtime will use, for the Settings page."""
    profile = select_ocr_profile()
    return {
        "profile": profile.name,
        "device": profile.device,
        "gpu_enabled": profile.device.startswith("gpu"),
        # An NVIDIA driver without the CUDA runtime means the desktop app can
        # offer the downloadable GPU acceleration pack.
        "driver_available": _cuda_runtime_usable(),
    }


def paddlex_cache_dir() -> Path:
    """Resolve where PaddleOCR model downloads are stored."""
    configured = os.getenv("AGENT_OCR_CACHE_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path(load_agent_settings().local_models_root) / "paddleocr"


def configure_paddlex_cache() -> None:
    cache_dir = paddlex_cache_dir().resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(cache_dir))


__all__ = [
    "OcrProfile",
    "configure_paddlex_cache",
    "ocr_runtime_capability",
    "paddlex_cache_dir",
    "select_ocr_profile",
]
