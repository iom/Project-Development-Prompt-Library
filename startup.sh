#!/bin/bash

set -e

# If Oryx activates the venv, $VIRTUAL_ENV should be set.
if [ -n "$VIRTUAL_ENV" ]; then
  export PYTHONPATH="$VIRTUAL_ENV/lib/python3.11/site-packages:${PYTHONPATH}"
fi
# Set default port
PORT=${PORT:-8000}

# Change to app directory
#cd /home/site/wwwroot
pip install --upgrade pip
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
