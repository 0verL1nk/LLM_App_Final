"""Filesystem adapter for immutable uploaded documents."""

from pathlib import Path


def store_document_bytes(*, doc_uid: str, extension: str, content: bytes, upload_dir: str) -> str:
    root = Path(upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = (root / f"{doc_uid}{extension}").resolve()
    if root not in destination.parents:
        raise ValueError("Invalid upload path")
    destination.write_bytes(content)
    return str(destination)


__all__ = ["store_document_bytes"]
