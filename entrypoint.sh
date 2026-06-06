#!/bin/bash
set -e

echo "==> Running database migrations..."
python manage.py migrate --no-input

echo "==> Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 3 \
    --timeout 120