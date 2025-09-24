#!/bin/bash

set -e

# Set default port
PORT=${PORT:-8000}

# Change to app directory
cd /home/site/wwwroot

# Install dependencies
pip install -r requirements.txt

# Create tables and start server
python -c "
from sqlmodel import SQLModel
from app.database import engine
SQLModel.metadata.create_all(engine)
print('Database initialized')
"

# Start FastAPI application
exec python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT