#!/bin/sh
# Serveur de développement local : http://localhost:5010
set -e
cd "$(dirname "$0")"
export CV_DATA_DIR=./data CV_ROLE="${CV_ROLE:-public}"
.venv/bin/alembic upgrade head
.venv/bin/flask --app cv.app amorcer
exec .venv/bin/flask --app cv.app run --port 5010 --debug
