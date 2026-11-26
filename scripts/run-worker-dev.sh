#!/usr/bin/env bash
set -euo pipefail
cd /home/maadec/infra/aivancity-dev
set -a
source .env
set +a
export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}"
cd api
exec ../.aivancity-venv/bin/python -m app.worker
