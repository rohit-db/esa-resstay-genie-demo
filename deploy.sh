#!/usr/bin/env bash
# One-command deployment. Example: ./deploy.sh --profile esa-resstay-demo --target demo
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Create the environment first: uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt" >&2
  exit 1
fi
exec .venv/bin/python tools/deploy.py "$@"
