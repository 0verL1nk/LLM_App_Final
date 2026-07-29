UV ?= uv
UVX ?= uvx
PYTHON := $(UV) run --extra dev python
PYTEST := $(PYTHON) -m pytest
RUFF := $(UV) run --extra dev ruff
CORE_PATHS := api agent/domain agent/tools agent/application/contracts.py
SPEC ?= refactor-multi-agent-system

EVAL_FIXTURE ?= tests/evals/fixtures/agent_task_eval_set_v1.jsonl
EVAL_ENV_FILE ?= .env
EVAL_CASE_ID ?=
EVAL_LIMIT ?= 1
EVAL_OUTPUT ?=
AGENT_LLM_REQUEST_TIMEOUT ?=
JUDGE_MODEL ?=
JUDGE_BASE_URL ?=
export AGENT_LLM_REQUEST_TIMEOUT

LIVE_SMOKE_CASE_ARG := $(if $(strip $(EVAL_CASE_ID)),--case-id $(EVAL_CASE_ID),)
LIVE_SMOKE_OUTPUT_ARG := $(if $(strip $(EVAL_OUTPUT)),--output $(EVAL_OUTPUT),)
BASELINE_JUDGE_MODEL_ARG := $(if $(strip $(JUDGE_MODEL)),--judge-model $(JUDGE_MODEL),)
BASELINE_JUDGE_BASE_URL_ARG := $(if $(strip $(JUDGE_BASE_URL)),--judge-base-url $(JUDGE_BASE_URL),)
BASELINE_CASE_ARG := $(if $(strip $(EVAL_CASE_ID)),--case-id $(EVAL_CASE_ID),)
BASELINE_LIMIT_ARG := $(if $(strip $(EVAL_LIMIT)),--limit $(EVAL_LIMIT),)
BASELINE_OUTPUT_ARG := $(if $(strip $(EVAL_OUTPUT)),--output $(EVAL_OUTPUT),)

.DEFAULT_GOAL := help

.PHONY: help install install-dev web-install lock-check run dev serve api-dev web-dev web-build web-test web-lint web-typecheck desktop-dev desktop-package desktop-package-win desktop-package-mac desktop-package-linux browser-cdp \
	test test-all test-unit test-integration test-evals test-coverage \
	lint lint-core format format-check typecheck typecheck-core \
	quality-core quality-full quality-unused check ci spec-validate spec-validate-all \
	cleanup-check cleanup-fix cleanup-deadcode cleanup-whitelist \
	eval-baseline eval-baseline-judge eval-live-smoke

help: ## Show available development commands.
	@$(UV) run python -c "from pathlib import Path; rows=[(line.split(':', 1)[0], line.split('##', 1)[1].strip()) for line in Path('Makefile').read_text(encoding='utf-8').splitlines() if ':' in line and '##' in line and not line[0].isspace()]; print('PaperSage development commands:\n'); print('\n'.join(f'  {name:<22} {description}' for name, description in rows))"

install: ## Sync runtime dependencies without installing the project package.
	$(UV) sync --no-install-project

install-dev: ## Sync runtime and development dependencies.
	$(UV) sync --extra dev --no-install-project

lock-check: ## Verify that uv.lock matches pyproject.toml.
	$(UV) lock --check

run: ## Start API :8000 and Vite :5173 together for local development.
	$(PYTHON) scripts/dev_server.py

dev: run ## Alias for make run.

serve: ## Start the production FastAPI server (serves the built web/dist).
	$(UV) run python -m api.main

api-dev: ## Start the FastAPI server with reload.
	$(UV) run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

web-dev: ## Start the Vite frontend development server.
	npm --prefix web run dev

web-install: ## Install locked frontend dependencies.
	npm --prefix web ci

web-build: ## Type-check and build the production frontend.
	npm --prefix web run build

web-test: ## Run frontend unit tests.
	npm --prefix web run test

web-lint: ## Lint frontend TypeScript and React code.
	npm --prefix web run lint

web-typecheck: ## Type-check frontend code without emitting files.
	npm --prefix web run typecheck

desktop-dev: ## Launch the Electron desktop shell with the local API.
	npm --prefix web run desktop:dev

desktop-package: ## Build a Windows installer containing the frontend and Python API.
	npm --prefix web run desktop:package

desktop-package-win: ## Build the Windows NSIS installer.
	npm --prefix web run desktop:package:win

desktop-package-mac: ## Build the macOS DMG on macOS.
	npm --prefix web run desktop:package:mac

desktop-package-linux: ## Build AppImage and deb packages on Linux.
	npm --prefix web run desktop:package:linux

browser-cdp: ## Start isolated Chrome with a stable CDP port for local browser tests (Windows).
	powershell -ExecutionPolicy Bypass -File scripts/start_browser_cdp.ps1

test: test-all ## Run the complete offline test suite.

test-all: ## Run unit, integration, and offline eval tests.
	$(PYTEST) tests/unit tests/integration tests/evals -q

test-unit: ## Run fast unit tests.
	$(PYTEST) tests/unit -q

test-integration: ## Run integration tests; live tests remain opt-in by markers/config.
	$(PYTEST) tests/integration -q

test-evals: ## Validate eval fixtures, contracts, and offline runners.
	$(PYTEST) tests/evals -q

test-coverage: ## Run tests with terminal and XML coverage reports.
	$(PYTEST) tests/unit tests/integration tests/evals --cov=agent --cov=ui --cov-report=term-missing --cov-report=xml

lint: ## Run repository-wide Ruff checks without modifying files.
	$(RUFF) check .
	$(PYTHON) scripts/python_cleanup.py check

lint-core: ## Run Ruff on the blocking core scope.
	$(RUFF) check $(CORE_PATHS)

format: ## Apply Ruff formatting and safe lint fixes explicitly.
	$(PYTHON) scripts/python_cleanup.py fix-safe
	$(RUFF) check . --fix
	$(RUFF) format .

format-check: ## Check formatting without modifying files.
	$(RUFF) format . --check

typecheck: ## Type-check the API and full agent package.
	$(UVX) ty check api agent

typecheck-core: ## Type-check the blocking core scope.
	$(UVX) ty check $(CORE_PATHS)

quality-core: lint-core typecheck-core ## Run blocking core lint and type checks.

quality-full: lint typecheck web-lint web-typecheck ## Run Python and frontend quality checks.

quality-unused: ## Report unused imports, variables, and suspected dead code.
	$(PYTHON) scripts/python_cleanup.py check
	$(PYTHON) scripts/python_cleanup.py deadcode

spec-validate: ## Strictly validate one OpenSpec item (SPEC=refactor-multi-agent-system).
	openspec validate $(SPEC) --strict

spec-validate-all: ## Audit every OpenSpec item strictly, including legacy documents.
	openspec validate --all --strict

check: quality-core web-lint web-typecheck test-unit spec-validate ## Run the fast local pre-commit gate.

ci: lock-check quality-full web-test web-build test-all spec-validate ## Run the complete offline CI gate.

cleanup-check: ## Check imports and variables without modifying files.
	$(PYTHON) scripts/python_cleanup.py check

cleanup-fix: ## Apply safe import and variable cleanup.
	$(PYTHON) scripts/python_cleanup.py fix-safe

cleanup-deadcode: ## Report suspected dead code for manual review.
	$(PYTHON) scripts/python_cleanup.py deadcode

cleanup-whitelist: ## Regenerate the dead-code review whitelist.
	$(PYTHON) scripts/python_cleanup.py deadcode --make-whitelist

eval-baseline: ## Run task-completion evals; configure with EVAL_* and JUDGE_* variables.
	$(PYTHON) tests/evals/run_agent_task_completion_baseline.py --fixture $(EVAL_FIXTURE) --env-file $(EVAL_ENV_FILE) $(BASELINE_JUDGE_MODEL_ARG) $(BASELINE_JUDGE_BASE_URL_ARG) $(BASELINE_CASE_ARG) $(BASELINE_LIMIT_ARG) $(BASELINE_OUTPUT_ARG)

eval-baseline-judge: eval-baseline ## Alias for baseline eval with optional judge overrides.

eval-live-smoke: ## Run a small live-model smoke eval; requires API credentials.
	$(PYTHON) tests/evals/run_agent_task_completion_live_smoke.py --fixture $(EVAL_FIXTURE) --env-file $(EVAL_ENV_FILE) --limit $(EVAL_LIMIT) $(LIVE_SMOKE_CASE_ARG) $(LIVE_SMOKE_OUTPUT_ARG)
