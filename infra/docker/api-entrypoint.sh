#!/bin/sh
set -eu

python -m cognitive_traffic.storage.bootstrap
exec uvicorn cognitive_traffic.api.main:app --host 0.0.0.0 --port "${PORT:-10000}"
