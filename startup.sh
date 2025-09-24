
#!/bin/bash

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "
from app.database import engine
from app.models import *
from sqlmodel import SQLModel
SQLModel.metadata.create_all(engine)
"

# Start the FastAPI application
uvicorn app.main:app --host 0.0.0.0 --port 8000
