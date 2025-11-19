#!/bin/bash
# Docker entrypoint script for API and Worker containers
# Runs database migrations before starting the service

set -e

echo "======================================"
echo "Acme Import Service - Starting"
echo "======================================"

# Create upload directory if it doesn't exist
mkdir -p /tmp/imports
echo "✓ Upload directory ready"

# Run database migrations
echo ""
echo "Running database migrations..."
python scripts/run_migrations.py

if [ $? -ne 0 ]; then
    echo "✗ Migration failed. Exiting."
    exit 1
fi

echo ""
echo "======================================"
echo "Starting service: $@"
echo "======================================"

# Execute the main command (passed as arguments)
exec "$@"

