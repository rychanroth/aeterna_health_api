#!/bin/bash
set -e

echo "==> Running database migrations..."
python manage.py migrate --no-input

python manage.py seed_dev

# 2. THE WORKAROUND: Programmatically create the superuser if the env vars exist
if [ "$DJANGO_SUPERUSER_USERNAME" ]; then
    echo "Creating superuser..."
    python manage.py createsuperuser --no-input || echo "Superuser already exists or failed."
fi

echo "==> Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 3 \
    --timeout 120