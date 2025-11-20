#!/bin/bash
# Startup script for Railway API service
# Runs migrations then starts uvicorn server

set -e  # Exit on any error

echo "======================================"
echo "Starting Acme API Service"
echo "======================================"

# Run Railway startup script (migrations)
python scripts/railway-startup.py

if [ $? -ne 0 ]; then
    echo "ERROR: Startup script failed!"
    exit 1
fi

# Get port from Railway environment or default to 8000
PORT=${PORT:-8000}

echo ""
echo "======================================"
echo "Starting uvicorn server on port $PORT"
echo "======================================"

# Start uvicorn with Railway's PORT
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"

