import argparse
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.adapters.llm import create_chat_model
from agent.adapters.rag import create_project_evidence_retriever
from agent.application.evals import (
    AgentEvalCase,
    build_trajectory_llm_as_judge,
    load_eval_cases,
    run_agent_evals,
    select_eval_cases,
)
from agent.application.evals.live_harness import LivePaperSageEvalRunner
from agent.application.turn_engine import execute_turn_core
from agent.profiles import paper_leader_profile
from agent.prompts.paper_domain import build_external_research_prompt
from agent.session_factory import AgentDependencies, AgentRuntimeOptions, create_agent_session

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "papers" / "rag_agentic_reasoning"


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line or line.startswith("export "):
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _paper_uid_from_fixture_name(name: str) -> str:
    stem = Path(name).stem
    paper_id = stem.split("-", 1)[0].strip() if "-" in stem else stem.strip()
    return f"arxiv:{paper_id}"


def _paper_title_from_fixture_name(name: str) -> str:
    stem = Path(name).stem
    if "-" not in stem:
        return stem
    return stem.split("-", 1)[1].replace("-", " ").strip()


def _load_project_documents(max_chars_per_doc: int = 30000) -> list[dict[str, str]]:
    cache_dir = FIXTURE_DIR / "_extracted"
    docs: list[dict[str, str]] = []
    for text_path in sorted(cache_dir.glob("*.txt")):
        extracted = text_path.read_text(encoding="utf-8", errors="replace").strip()
        if not extracted:
            continue
        paper_id = _paper_uid_from_fixture_name(text_path.name)
        title = _paper_title_from_fixture_name(text_path.name)
        docs.append(
            {
                "doc_uid": paper_id,
                "doc_name": title,
                "text": (
                    f"[paper_id] {paper_id}\n"
                    f"[title] {title}\n"
                    f"[source_file] {text_path.name}\n\n"
                    f"{extracted[:max_chars_per_doc]}"
                ),
            }
        )
    if not docs:
        raise ValueError("No local paper fixture texts found for live eval smoke run.")
    return docs


def _build_live_llm() -> Any:
    api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    model_name = str(os.getenv("OPENAI_MODEL_NAME") or "").strip()
    base_url = str(os.getenv("OPENAI_BASE_URL") or "").strip()
    missing = [
        key
        for key, value in {
            "OPENAI_API_KEY": api_key,
            "OPENAI_MODEL_NAME": model_name,
            "OPENAI_BASE_URL": base_url,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing live eval config: {', '.join(missing)}")
    return create_chat_model(
        api_key=api_key,
        model_name=model_name,
        base_url=base_url,
        temperature=0.0,
    )


def _default_output_path() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path("docs/plans/baselines") / f"task-completion-live-smoke-{stamp}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a small live PaperSage task-completion eval smoke test.")
    parser.add_argument(
        "--fixture",
        default="tests/evals/fixtures/agent_task_eval_set_v1.jsonl",
        help="Path to eval fixture JSONL.",
    )
    parser.add_argument(
        "--env-file",
        default="/home/ling/LLM_App_Final/.env",
        help="Path to env file with live LLM configuration.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path. Defaults to docs/plans/baselines/task-completion-live-smoke-<timestamp>.json",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Optional case id to run. Repeat to run multiple cases.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of cases to run after filtering. 0 (default) runs all selected cases.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Trials per case; >1 enables pass^k gating (a case passes only if all trials pass).",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Concurrent cases; results stay in fixture order.",
    )
    parser.add_argument(
        "--web-fixture",
        default="",
        help="Web fixture name: replay mode without --record-web, capture target with it.",
    )
    parser.add_argument(
        "--record-web",
        action="store_true",
        help="Record live web results into --web-fixture (default name 'v1') instead of replaying.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="With --record-web: discard existing entries and re-capture.",
    )
    parser.add_argument(
        "--dump-trajectories",
        default="",
        help="Write per-case turn results to this JSONL for later offline judging.",
    )
    parser.add_argument(
        "--judge-trajectories",
        default="",
        help="Offline mode: judge a dumped trajectory JSONL instead of running the agent.",
    )
    parser.add_argument(
        "--judge-model",
        default="",
        help="Optional judge model override; defaults to OPENAI_MODEL_NAME (same as agent).",
    )
    parser.add_argument(
        "--judge-base-url",
        default="",
        help="Optional judge base URL override; defaults to OPENAI_BASE_URL.",
    )
    args = parser.parse_args()

    _load_env_file(Path(args.env_file))

    fixture_name = args.web_fixture.strip() or ("v1" if args.record_web else "")
    web_fixture_checksum = ""
    if args.record_web:
        from agent.application.evals import web_fixture

        web_fixture.activate_record(fixture_name, refresh=args.refresh)
    elif fixture_name:
        from agent.application.evals import web_fixture

        web_fixture_checksum = web_fixture.activate_replay(fixture_name)

    fixture_path = Path(args.fixture)
    output_path = Path(args.output) if args.output else _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cases = load_eval_cases(fixture_path)
    cases = select_eval_cases(
        cases,
        case_ids=args.case_id or None,
        limit=args.limit if args.limit > 0 else None,
    )
    if not cases:
        raise ValueError("No eval cases selected for live smoke run.")

    judge_model_name = args.judge_model.strip() or str(os.getenv("OPENAI_MODEL_NAME") or "")
    judge_base_url = args.judge_base_url.strip() or str(os.getenv("OPENAI_BASE_URL") or "")

    if args.judge_trajectories:
        # Offline judging (two-stage eval): reuse dumped turn results, only
        # the judge runs - no agent execution, no document corpus needed.
        with open(args.judge_trajectories, encoding="utf-8") as handle:
            trajectories = {
                row["case_id"]: row["turn_result"]
                for row in (json.loads(line) for line in handle if line.strip())
            }
        cases = [case for case in cases if case.case_id in trajectories]
        judge_llm = create_chat_model(
            api_key=str(os.getenv("OPENAI_API_KEY") or ""),
            model_name=judge_model_name,
            base_url=judge_base_url or None,
            temperature=0.0,
        )
        judge = build_trajectory_llm_as_judge(model=judge_llm)

        def _offline_runner(case: Any) -> dict[str, Any]:
            return trajectories[case.case_id]

        report = run_agent_evals(
            cases,
            runner=_offline_runner,
            judge=judge,
            fixture_path=str(fixture_path),
            run_config={
                "runner_mode": "offline_judge",
                "judge_model": judge_model_name,
                "trajectories": args.judge_trajectories,
            },
        )
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"offline judge: {report['completed_cases']}/{report['total_cases']} | report: {output_path}")
        return 0

    documents = _load_project_documents()
    llm = _build_live_llm()
    judge_llm = (
        llm
        if judge_model_name == str(os.getenv("OPENAI_MODEL_NAME") or "")
        and not args.judge_base_url.strip()
        else create_chat_model(
            api_key=str(os.getenv("OPENAI_API_KEY") or ""),
            model_name=judge_model_name,
            base_url=judge_base_url or None,
            temperature=0.0,
        )
    )
    judge = build_trajectory_llm_as_judge(model=judge_llm)
    activity_counters: dict[str, dict[str, int]] = {}

    def _on_activity(case_id: str, event: dict) -> None:
        performative = str(event.get("performative") or "")
        if performative not in {"tool_call", "tool_result"}:
            return
        counters = activity_counters.setdefault(case_id, {"tool_calls": 0, "tool_results": 0})
        if performative == "tool_call":
            counters["tool_calls"] += 1
        else:
            counters["tool_results"] += 1
        for item in progress_state["cases"]:
            if item["case_id"] == case_id:
                item["activity"] = {
                    **counters,
                    "last": performative,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
        _flush_progress()

    runner = LivePaperSageEvalRunner(
        llm=llm,
        documents=documents,
        project_name="Task Completion Live Smoke",
        on_activity=_on_activity,
    )

    # Progress bridge: CLI runs write a snapshot beside the report so the
    # dev evals page can display them live (the in-app registry only knows
    # about runs started via the API service).
    progress_path = output_path.with_suffix(".progress.json")
    progress_state: dict[str, Any] = {
        "uid": output_path.stem,
        "status": "running",
        "fixture_path": str(fixture_path),
        "trials": max(1, int(args.repeat)),
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
        "total_cases": len(cases),
        "finished_cases": 0,
        "completed_cases": 0,
        "case_ids": [case.case_id for case in cases],
        "cases": [
            {"case_id": case.case_id, "category": case.category, "status": "pending",
             "started_at": None, "finished_at": None, "summary": {}}
            for case in cases
        ],
        "report": None,
        "artifact_path": str(output_path),
        "error": None,
    }

    def _flush_progress() -> None:
        progress_path.write_text(
            json.dumps(progress_state, ensure_ascii=False), encoding="utf-8"
        )

    def _on_progress_start(case_id: str) -> None:
        for item in progress_state["cases"]:
            if item["case_id"] == case_id:
                item["status"] = "running"
                item["started_at"] = datetime.now(UTC).isoformat()
        _flush_progress()

    def _on_progress_result(case_id: str, result: dict[str, Any]) -> None:
        summary = {
            key: result.get("process_checks", {}).get(key)
            for key in ("delegation_count", "max_delegations_per_message")
        }
        coverage = result.get("evidence_coverage") or {}
        diagnostics = result.get("diagnostics") or {}
        summary.update(
            {
                "completed": bool(result.get("completed")),
                "final_success": bool(result.get("final_success")),
                "process_success": bool(result.get("process_success")),
                "evidence_count": coverage.get("count"),
                "evidence_required": coverage.get("required_count"),
                "run_latency_ms": diagnostics.get("run_latency_ms"),
                "total_tool_calls": diagnostics.get("total_tool_calls"),
                "error_type": diagnostics.get("error_type"),
                "failure_reason": (result.get("feedback") or {}).get("failure_reason"),
            }
        )
        trials_info = result.get("trials")
        if trials_info:
            summary["trials"] = trials_info
        for item in progress_state["cases"]:
            if item["case_id"] == case_id:
                item["status"] = (
                    "errored" if summary.get("error_type")
                    else ("passed" if summary.get("completed") else "failed")
                )
                item["finished_at"] = datetime.now(UTC).isoformat()
                item["summary"] = summary
        progress_state["finished_cases"] = sum(
            1 for item in progress_state["cases"]
            if item["status"] in {"passed", "failed", "errored"}
        )
        progress_state["completed_cases"] = sum(
            1 for item in progress_state["cases"] if item["status"] == "passed"
        )
        _flush_progress()

    _flush_progress()

    trajectory_rows: list[dict[str, Any]] = []
    live_runner = runner

    def _runner_with_trajectory_dump(case: AgentEvalCase) -> dict[str, Any]:
        result = live_runner(case)
        trajectory_rows.append({"case_id": case.case_id, "turn_result": result})
        return result

    report = run_agent_evals(
        cases,
        runner=_runner_with_trajectory_dump if args.dump_trajectories else runner,
        judge=judge,
        fixture_path=str(fixture_path),
        trials=max(1, int(args.repeat)),
        parallel=max(1, int(args.parallel)),
        on_case_start=_on_progress_start,
        on_case_result=_on_progress_result,
        run_config={
            "runner_mode": "live_model",
            "agent_model": str(os.getenv("OPENAI_MODEL_NAME") or ""),
            "judge_model": judge_model_name,
            "web_fixture": (
                {"name": fixture_name, "mode": "record", "refresh": args.refresh}
                if args.record_web
                else ({"name": fixture_name, "checksum": web_fixture_checksum} if fixture_name else None)
            ),
            "web_search_fallback": bool(os.getenv("AGENT_WEB_ENABLE_DDG_FALLBACK")),
            "document_corpus": str(FIXTURE_DIR),
            "delegation_note": (
                "turn-level harness: delegate_task returns durable_run_required; "
                "delegation contracts measure leader behavior only"
            ),
        },
    )
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.dump_trajectories:
        Path(args.dump_trajectories).write_text(
            "\n".join(
                json.dumps(row, ensure_ascii=False, default=str)
                for row in trajectory_rows
            )
            + ("\n" if trajectory_rows else ""),
            encoding="utf-8",
        )
        print(f"trajectories: {args.dump_trajectories} ({len(trajectory_rows)} cases)")

    progress_state["status"] = "completed"
    progress_state["finished_at"] = datetime.now(UTC).isoformat()
    progress_state["report"] = {
        "completion_rate": report.get("completion_rate"),
        "final_success_rate": report.get("final_success_rate"),
        "process_success_rate": report.get("process_success_rate"),
        "evidence_coverage_rate": report.get("evidence_coverage_rate"),
    }
    _flush_progress()

    print(f"fixture: {fixture_path}")
    print(f"cases: {report['total_cases']}")
    print(f"selected_case_ids: {[item['case_id'] for item in report['cases']]}")
    print(f"completed_cases: {report['completed_cases']}")
    print(f"completion_rate: {report['completion_rate']:.3f}")
    print(f"remediation_area_counts: {report['remediation_area_counts']}")
    print(f"report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
