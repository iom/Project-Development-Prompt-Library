#!/bin/bash
# Azure App Service startup script
echo "Starting FastAPI application on Azure..."

# Set default port if not provided by Azure
PORT=${PORT:-8000}
echo "Using port: $PORT"

# Start the application
uvicorn app.main:app --host 0.0.0.0 --port $PORT