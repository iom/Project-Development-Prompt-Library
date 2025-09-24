
#!/bin/bash
# Azure App Service startup script
echo "Starting FastAPI application on Azure..."

# Set default port if not provided by Azure
PORT=${PORT:-8000}
echo "Using port: $PORT"

# Change to the application directory
cd /home/site/wwwroot

# Add current directory to Python path for module imports
export PYTHONPATH="/home/site/wwwroot:/home/site/wwwroot/app:$PYTHONPATH"

# Create __init__.py in app directory if it doesn't exist
if [ ! -f "app/__init__.py" ]; then
    touch app/__init__.py
    echo "Created app/__init__.py"
fi

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
echo "Current PYTHONPATH: $PYTHONPATH"
echo "Current working directory: $(pwd)"
echo "Contents of current directory:"
ls -la

python -c "
import sys
print('Python path:')
for path in sys.path:
    print(f'  {path}')

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
    print('Attempting to add app directory to sys.path...')
    sys.path.insert(0, '/home/site/wwwroot')
    try:
        import app.main
        print('✓ App module imported after path fix')
    except ImportError as e2:
        print(f'✗ Still cannot import app: {e2}')
        exit(1)
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
    print('Skipping database initialization - app will handle it on startup')
"

# Start the application
echo "Starting FastAPI server on port $PORT..."
echo "Working directory: $(pwd)"
echo "Python path: $PYTHONPATH"

# Debug directory structure
echo "=== Comprehensive Directory Debug ==="
echo "Current working directory: $(pwd)"
echo "HOME: $HOME"
echo "Root directory contents:"
ls -la /home/site/wwwroot/ 2>/dev/null || ls -la
echo ""

# Ensure we're in the right directory
cd /home/site/wwwroot 2>/dev/null || cd /

echo "After CD - Current directory: $(pwd)"
echo "Contents:"
ls -la
echo ""

# Look for app directory and main.py
echo "Searching for app directory and main.py..."
find . -name "app" -type d 2>/dev/null || echo "No app directory found"
find . -name "main.py" -type f 2>/dev/null || echo "No main.py files found"
echo ""

# Check specific paths
echo "Checking specific file paths:"
echo "- ./app/main.py: $([ -f './app/main.py' ] && echo 'EXISTS' || echo 'NOT FOUND')"
echo "- /home/site/wwwroot/app/main.py: $([ -f '/home/site/wwwroot/app/main.py' ] && echo 'EXISTS' || echo 'NOT FOUND')"
echo "- ./main.py: $([ -f './main.py' ] && echo 'EXISTS' || echo 'NOT FOUND')"
echo ""

# Try to start the application with multiple strategies
if [ -f "./app/main.py" ]; then
    echo "✓ Found ./app/main.py - Strategy 1: Direct path"
    export PYTHONPATH="$(pwd):$(pwd)/app:$PYTHONPATH"
    echo "Updated PYTHONPATH: $PYTHONPATH"
    exec python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
elif [ -f "/home/site/wwwroot/app/main.py" ]; then
    echo "✓ Found /home/site/wwwroot/app/main.py - Strategy 2: Full path"
    cd /home/site/wwwroot
    export PYTHONPATH="/home/site/wwwroot:/home/site/wwwroot/app:$PYTHONPATH"
    echo "Updated PYTHONPATH: $PYTHONPATH"
    exec python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
elif [ -f "./main.py" ]; then
    echo "✓ Found ./main.py in root - Strategy 3: Root level"
    export PYTHONPATH="$(pwd):$PYTHONPATH"
    exec python -m uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1
else
    echo "✗ Cannot locate FastAPI application using any strategy"
    echo ""
    echo "=== Final Debug Information ==="
    echo "All directories:"
    find . -type d 2>/dev/null | head -20
    echo ""
    echo "All Python files:"
    find . -name "*.py" -type f 2>/dev/null | head -20
    echo ""
    echo "Complete directory tree:"
    ls -laR . 2>/dev/null | head -50
    exit 1
fi
