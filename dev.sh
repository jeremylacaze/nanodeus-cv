#!/bin/sh
# Serveur de développement local : http://localhost:5010
# Admin : CV_ROLE=admin CV_PORT=5011 ./dev.sh, puis http://localhost:5011/admin/
set -e
cd "$(dirname "$0")"
export CV_DATA_DIR=./data CV_ROLE="${CV_ROLE:-public}"
.venv/bin/alembic upgrade head
.venv/bin/flask --app cv.app amorcer
exec .venv/bin/flask --app cv.app run --port "${CV_PORT:-5010}" --debug
