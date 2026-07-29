from pathlib import Path

from agent.adapters.sqlite.project_repository import create_project, list_project_files
from agent.application.document_library import upload_project_document


def test_upload_project_document_persists_binds_and_enqueues(tmp_path: Path) -> None:
    db_name = str(tmp_path / "papersage.sqlite")
    project = create_project(
        uuid="u1",
        project_name="Research",
        db_name=db_name,
    )
    queued_calls: list[tuple[object, ...]] = []

    def enqueue(_task, *args):
        queued_calls.append(args)
        return {"mode": "queued", "job_id": "job-1"}

    uploaded = upload_project_document(
        project_uid=str(project["project_uid"]),
        user_uuid="u1",
        file_name="paper.pdf",
        content=b"%PDF-test",
        enqueue_background_fn=enqueue,
        upload_dir=str(tmp_path / "uploads"),
        db_name=db_name,
    )

    documents = list_project_files(
        project_uid=str(project["project_uid"]),
        uuid="u1",
        active_only=False,
        db_name=db_name,
    )
    assert uploaded["file_name"] == "paper.pdf"
    assert Path(str(uploaded["file_path"])).read_bytes() == b"%PDF-test"
    assert documents[0]["uid"] == uploaded["uid"]
    assert queued_calls


def test_upload_project_document_rejects_unsupported_extension(tmp_path: Path) -> None:
    db_name = str(tmp_path / "papersage.sqlite")
    project = create_project(uuid="u1", project_name="Research", db_name=db_name)

    try:
        upload_project_document(
            project_uid=str(project["project_uid"]),
            user_uuid="u1",
            file_name="payload.exe",
            content=b"bad",
            enqueue_background_fn=lambda *_args: {},
            db_name=db_name,
        )
    except ValueError as exc:
        assert "Unsupported" in str(exc)
    else:
        raise AssertionError("unsupported upload was accepted")
