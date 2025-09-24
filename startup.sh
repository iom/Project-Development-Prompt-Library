
#!/bin/bash

# Set environment variables for Azure
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot"

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
fi

# Initialize database
echo "Initializing database..."
python -c "
from app.database import engine
from app.models import *
from sqlmodel import SQLModel
SQLModel.metadata.create_all(engine)
print('Database initialized successfully')
"

# Start the FastAPI application
echo "Starting FastAPI application..."
uvicorn app.main:app --host 0.0.0.0 --port 8000
