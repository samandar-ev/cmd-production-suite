#!/bin/sh
set -e
python backend/manage.py migrate --noinput
python backend/manage.py flushexpiredtokens || true
exec gunicorn --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --worker-class gthread --threads 4 \
  --timeout 120 --pythonpath backend cmd_agency.wsgi:application
