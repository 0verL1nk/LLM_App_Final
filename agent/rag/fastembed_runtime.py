"""Shared FastEmbed construction with partial-download self-healing."""

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings



def _is_missing_model_error(exc: BaseException) -> bool:
    message = str(exc)
    return "NO_SUCHFILE" in message or "File doesn't exist" in message


def _model_cache_dir(cache_dir: str, model_name: str) -> Path:
    org, _, name = model_name.partition("/")
    return Path(cache_dir) / f"models--{org}--{name}"


def build_fastembed_embeddings(*, model_name: str, cache_dir: str) -> "FastEmbedEmbeddings":
    # Deferred for startup cost; see agent/embedding_provider.py.
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    try:
        return FastEmbedEmbeddings(model_name=model_name, cache_dir=cache_dir)
    except Exception as exc:
        if not _is_missing_model_error(exc):
            raise
        # An interrupted download leaves the HuggingFace snapshot directory
        # behind while hub metadata still reports completion, so every later
        # init fails to open model_optimized.onnx. Drop the model's cache
        # subtree once and let this init download it again.
        shutil.rmtree(_model_cache_dir(cache_dir, model_name), ignore_errors=True)
        return FastEmbedEmbeddings(model_name=model_name, cache_dir=cache_dir)


__all__ = ["build_fastembed_embeddings"]
