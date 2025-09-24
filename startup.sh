#!/bin/bash
# Azure App Service startup script for FastAPI application

# Set default port if not provided by Azure
PORT=${PORT:-8000}
echo "Starting FastAPI application on port $PORT..."

# Change to the application directory
cd /home/site/wwwroot

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies from requirements.txt..."
    python -m pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "Warning: requirements.txt not found, installing core dependencies..."
    pip install fastapi uvicorn sqlmodel azure-storage-blob azure-core jinja2 python-multipart python-slugify requests alembic aiohttp
fi

# Add current directory to Python path
export PYTHONPATH="/home/site/wwwroot:$PYTHONPATH"

# Create app/__init__.py if it doesn't exist
mkdir -p app
touch app/__init__.py

# Initialize database
echo "Initializing database..."
python -c "
try:
    from app.database import engine
    from sqlmodel import SQLModel
    SQLModel.metadata.create_all(engine)
    print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization warning: {e}')
"

# Start the FastAPI application
echo "Starting FastAPI server..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT