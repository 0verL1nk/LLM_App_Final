from .application.a2ui_output_contract import build_a2ui_output_contract
from .prompts import (
    build_base_agent_prompt,
    build_leader_role_prompt,
    build_paper_domain_prompt,
    build_reviewer_role_prompt,
    build_worker_role_prompt,
)


def _join_prompt_sections(*sections: str) -> str:
    return "\n\n".join(section.strip() for section in sections if section and section.strip())


def build_paper_system_prompt(
    document_name: str | None = None,
    project_name: str | None = None,
    scope_summary: str | None = None,
) -> str:
    return _join_prompt_sections(
        build_base_agent_prompt(),
        build_paper_domain_prompt(
            document_name=document_name,
            project_name=project_name,
            scope_summary=scope_summary,
        ),
        build_a2ui_output_contract(),
        build_leader_role_prompt(),
    )


def build_paper_worker_prompt(
    document_name: str | None = None,
    project_name: str | None = None,
    scope_summary: str | None = None,
) -> str:
    return _join_prompt_sections(
        build_base_agent_prompt(),
        build_paper_domain_prompt(
            document_name=document_name,
            project_name=project_name,
            scope_summary=scope_summary,
        ),
        build_worker_role_prompt(),
    )


def build_paper_reviewer_prompt(
    document_name: str | None = None,
    project_name: str | None = None,
    scope_summary: str | None = None,
) -> str:
    return _join_prompt_sections(
        build_base_agent_prompt(),
        build_paper_domain_prompt(
            document_name=document_name,
            project_name=project_name,
            scope_summary=scope_summary,
        ),
        build_reviewer_role_prompt(),
    )


PAPER_QA_SYSTEM_PROMPT = build_paper_system_prompt()
