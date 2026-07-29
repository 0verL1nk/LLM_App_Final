#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-core}"
UV="${UV_BIN:-uv}"
UVX="${UVX_BIN:-uvx}"

case "${MODE}" in
  core)
    echo "[quality][core] ruff check (core scope)"
    "${UV}" run --extra dev ruff check api agent/domain agent/tools agent/application/contracts.py
    echo "[quality][core] ty (core scope)"
    "${UVX}" ty check api agent/domain agent/tools agent/application/contracts.py
    ;;
  full)
    echo "[quality][full] ruff check (full repo)"
    "${UV}" run --extra dev ruff check .
    echo "[quality][full] ty (full agent package)"
    "${UVX}" ty check api agent
    ;;
  unused)
    echo "[quality][unused] unused imports and variables"
    "${UV}" run --extra dev python scripts/python_cleanup.py check
    echo "[quality][unused] suspected dead code report"
    "${UV}" run --extra dev python scripts/python_cleanup.py deadcode
    ;;
  *)
    echo "Usage: bash scripts/quality_gate.sh [core|full|unused]"
    exit 2
    ;;
esac
