#!/usr/bin/env bash
set -euo pipefail

environment_name="${1:-traffic}"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda is required but was not found on PATH" >&2
  exit 1
fi

if ! conda env list | awk '{print $1}' | grep -Fxq "$environment_name"; then
  conda create --name "$environment_name" python=3.11 pip -y
fi

conda run --name "$environment_name" python -m pip install --upgrade pip
conda run --name "$environment_name" python -m pip install -e ".[dev]"
conda run --name "$environment_name" python --version
