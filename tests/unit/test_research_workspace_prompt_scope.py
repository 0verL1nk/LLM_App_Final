from agent.application.research_workspace import ResearchWorkspaceService


def test_workspace_prompt_scope_does_not_embed_document_names(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Evidence:
        def update_scope(self, _scope):
            return None

        def search_text(self, _query):
            return ""

        def search(self, _query):
            return {}

        def list_documents(self):
            return []

        def read_document(self, *_args):
            return "", 0

    class _Session:
        def close(self):
            return None

    monkeypatch.setattr("agent.application.research_workspace.require_project", lambda **_kwargs: {"project_name": "项目"})
    monkeypatch.setattr("agent.application.research_workspace.list_project_sessions", lambda **_kwargs: [{"session_uid": "session"}])
    monkeypatch.setattr("agent.application.research_workspace.list_project_files", lambda **_kwargs: [{"uid": "doc-1", "file_name": "不应进入提示词.pdf"}])
    monkeypatch.setattr("agent.application.research_workspace.read_api_key_for_user", lambda **_kwargs: "key")
    monkeypatch.setattr("agent.application.research_workspace.read_model_name_for_user", lambda **_kwargs: "model")
    monkeypatch.setattr("agent.application.research_workspace.read_base_url_for_user", lambda **_kwargs: "")
    monkeypatch.setattr("agent.application.research_workspace.DynamicProjectEvidenceService", lambda **_kwargs: _Evidence())
    monkeypatch.setattr("agent.application.research_workspace.build_openai_compatible_chat_model", lambda **_kwargs: object())
    monkeypatch.setattr("agent.application.research_workspace.create_agent_session", lambda **kwargs: captured.update(kwargs) or _Session())

    ResearchWorkspaceService()._runtime(project_uid="project", session_uid="session", user_uuid="user")

    options = captured["options"]
    assert options.document_name is None
    assert "不应进入提示词.pdf" not in options.scope_summary
