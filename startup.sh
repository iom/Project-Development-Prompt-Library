#!/bin/bash
# Azure App Service startup script
echo "Starting FastAPI application on Azure..."

# Set default port if not provided by Azure
PORT=${PORT:-8000}
echo "Using port: $PORT"

# Change to the application directory
cd /home/site/wwwroot

# Install dependencies if not already installed
echo "Checking Python dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

# Initialize database and create tables
echo "Initializing database..."
python -c "
from app.database import engine
from sqlmodel import SQLModel
print('Creating database tables...')
SQLModel.metadata.create_all(engine)
print('Database initialization complete')
"

# Start the application with proper error handling
echo "Starting FastAPI server on port $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1