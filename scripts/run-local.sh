#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

if [ -f local.env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./local.env
  set +a
fi

exec uv run python -m trendradar "$@"
