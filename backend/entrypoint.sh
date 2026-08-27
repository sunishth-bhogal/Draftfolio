#!/usr/bin/env bash
set -euo pipefail

# Apply migrations, then serve. Safe to run on every boot (no-op if up to date).
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
