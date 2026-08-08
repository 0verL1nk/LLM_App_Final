from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse

from api.routes import document_preview_page


def test_document_preview_serves_only_the_owned_rendered_page(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"pdf")
    preview = tmp_path / "previews" / "doc-1" / "page-00001.png"
    preview.parent.mkdir(parents=True)
    preview.write_bytes(b"png")
    monkeypatch.setattr(
        "api.routes.list_project_documents",
        lambda **_kwargs: [{"uid": "doc-1", "file_path": str(source)}],
    )

    response = document_preview_page("project-1", "doc-1", 1, "user-1")

    assert isinstance(response, FileResponse)
    assert Path(response.path) == preview
    assert response.media_type == "image/png"


def test_document_preview_rejects_unknown_document(monkeypatch) -> None:
    monkeypatch.setattr("api.routes.list_project_documents", lambda **_kwargs: [])

    with pytest.raises(HTTPException, match="Document not found") as error:
        document_preview_page("project-1", "other-doc", 1, "user-1")

    assert error.value.status_code == 404


def test_document_preview_requires_a_positive_page(monkeypatch) -> None:
    monkeypatch.setattr("api.routes.list_project_documents", lambda **_kwargs: [])

    with pytest.raises(HTTPException, match="Preview page not found") as error:
        document_preview_page("project-1", "doc-1", 0, "user-1")

    assert error.value.status_code == 404


def test_document_preview_rejects_a_path_like_document_identifier(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"pdf")
    monkeypatch.setattr(
        "api.routes.list_project_documents",
        lambda **_kwargs: [{"uid": "../other", "file_path": str(source)}],
    )

    with pytest.raises(HTTPException, match="Preview page not found") as error:
        document_preview_page("project-1", "../other", 1, "user-1")

    assert error.value.status_code == 404
