#!/bin/bash

set -e

if [ -n "${FILE_UPLOAD_TEMP_DIR:-}" ]; then
    mkdir -p "$FILE_UPLOAD_TEMP_DIR"
fi

python manage.py collectstatic --noinput

python manage.py compilemessages

exec "$@"
