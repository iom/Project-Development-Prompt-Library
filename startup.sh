#!/bin/bash
# Azure App Service startup script for FastAPI application

set -e  # Exit on any error

# Set default port if not provided by Azure
PORT=${PORT:-8000}
echo "Starting FastAPI application on port $PORT..."

# Ensure we're in the correct directory
cd /home/site/wwwroot

# Debug: Show what files exist
echo "=== Directory Structure ==="
ls -la
echo ""
echo "App directory contents:"
ls -la app/ 2>/dev/null || echo "app directory not found"
echo ""

# Install dependencies
echo "Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

# Set Python path
export PYTHONPATH="/home/site/wwwroot:$PYTHONPATH"
echo "PYTHONPATH set to: $PYTHONPATH"

# Ensure app module structure is correct
if [ -d "app" ]; then
    echo "App directory found"
    if [ -f "app/main.py" ]; then
        echo "app/main.py found"
    else
        echo "ERROR: app/main.py not found"
        exit 1
    fi
    
    if [ ! -f "app/__init__.py" ]; then
        echo "Creating app/__init__.py"
        touch app/__init__.py
    fi
else
    echo "ERROR: app directory not found"
    exit 1
fi

# Test import
echo "Testing import..."
python -c "import app.main; print('Import successful')" || {
    echo "ERROR: Cannot import app.main"
    python -c "import sys; print('Python path:', sys.path)"
    exit 1
}

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
echo "Starting uvicorn server..."
exec python -m uvicorn Project-Development-Prompt-Library.Project-Development-Prompt-Library.app.main:app --host 0.0.0.0 --port $PORT

