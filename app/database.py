from sqlmodel import SQLModel, Session, create_engine
from typing import Annotated
from fastapi import Depends

# SQLite database URL
DATABASE_URL = "sqlite:///./prompts.db"

# Create engine
engine = create_engine(DATABASE_URL, echo=True)

def get_session():
    with Session(engine) as session:
        yield session

# Dependency
SessionDep = Annotated[Session, Depends(get_session)]