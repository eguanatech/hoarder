#!/usr/bin/env bash
# Load PostgreSQL settings for the Django app.
# Usage: source ./use_postgres.sh

export USE_POSTGRES=1
export DB_NAME="${DB_NAME:-eguana}"
export DB_USER="${DB_USER:-djangouser}"
export DB_PASSWORD="${DB_PASSWORD:-Canada1234}"
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"

echo "PostgreSQL environment variables loaded."
