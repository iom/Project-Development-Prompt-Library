
#!/bin/bash
# Azure App Service startup script
echo "Starting FastAPI application on Azure..."

# Set default port if not provided by Azure
PORT=${PORT:-8000}
echo "Using port: $PORT"

# Change to the application directory
cd /home/site/wwwroot

# Add current directory to Python path for module imports
export PYTHONPATH="/home/site/wwwroot:$PYTHONPATH"

# Install dependencies
echo "Installing Python dependencies..."
python -m pip install --upgrade pip

# Install from requirements.txt (should exist from GitHub workflow)
echo "Current directory: $(pwd)"
echo "Files in current directory:"
ls -la

if [ -f "requirements.txt" ]; then
    echo "Found requirements.txt, installing dependencies..."
    cat requirements.txt
    pip install -r requirements.txt
elif [ -f "/home/site/wwwroot/requirements.txt" ]; then
    echo "Found requirements.txt in /home/site/wwwroot, installing dependencies..."
    pip install -r /home/site/wwwroot/requirements.txt
else
    echo "ERROR: requirements.txt not found in current directory or /home/site/wwwroot!"
    echo "Attempting to install core dependencies directly..."
    pip install fastapi uvicorn sqlmodel azure-storage-blob azure-core jinja2 python-multipart python-slugify requests alembic aiohttp
fi

# Verify critical modules can be imported
echo "Verifying module imports..."
python -c "
try:
    import azure.storage.blob
    print('✓ Azure Blob Storage module available')
except ImportError as e:
    print(f'✗ Azure module error: {e}')
    exit(1)

try:
    import app.main
    print('✓ App module can be imported')
except ImportError as e:
    print(f'✗ App import error: {e}')
    # Don't exit here, let uvicorn handle it
"

# Initialize database with proper error handling
echo "Initializing database..."
python -c "
import sys
sys.path.insert(0, '/home/site/wwwroot')

try:
    from app.database import engine
    from sqlmodel import SQLModel
    print('Creating database tables...')
    SQLModel.metadata.create_all(engine)
    print('✓ Database initialization complete')
except Exception as e:
    print(f'Database initialization error: {e}')
    # Continue anyway, app will handle it
"

# Start the application
echo "Starting FastAPI server on port $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
