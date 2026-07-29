from pathlib import Path

from agent.adapters.sqlite.project_repository import create_project, create_project_session, list_project_sessions
from agent.application import session_titles


class _TitleModel:
    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return {"title": "比较两种检索策略"}


def test_generate_session_title_names_an_untitled_session(monkeypatch, tmp_path: Path) -> None:
    db_path = str(tmp_path / "titles.sqlite")
    project = create_project(uuid="user-1", project_name="项目", db_name=db_path)
    session = create_project_session(project_uid=project["project_uid"], uuid="user-1", session_name="新探索", db_name=db_path)
    monkeypatch.setattr(session_titles, "read_api_key_for_user", lambda **_kwargs: "key")
    monkeypatch.setattr(session_titles, "read_model_name_for_user", lambda **_kwargs: "model")
    monkeypatch.setattr(session_titles, "read_base_url_for_user", lambda **_kwargs: "")
    monkeypatch.setattr(session_titles, "build_openai_compatible_chat_model", lambda **_kwargs: _TitleModel())

    session_titles.generate_session_title(user_uuid="user-1", project_uid=project["project_uid"], session_uid=session["session_uid"], prompt="比较检索", answer="这是比较结果", db_name=db_path)

    sessions = list_project_sessions(project_uid=project["project_uid"], uuid="user-1", db_name=db_path)
    assert sessions[0]["session_name"] == "比较两种检索策略"


def test_generate_session_title_does_not_overwrite_a_user_title(monkeypatch, tmp_path: Path) -> None:
    db_path = str(tmp_path / "titles.sqlite")
    project = create_project(uuid="user-1", project_name="项目", db_name=db_path)
    session = create_project_session(project_uid=project["project_uid"], uuid="user-1", session_name="我的命名", db_name=db_path)
    monkeypatch.setattr(session_titles, "build_openai_compatible_chat_model", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not call model")))

    session_titles.generate_session_title(user_uuid="user-1", project_uid=project["project_uid"], session_uid=session["session_uid"], prompt="问题", answer="回答", db_name=db_path)
