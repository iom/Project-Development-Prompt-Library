from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime
import json

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    role: str = Field(default="user")  # 'admin' or 'user'
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    slug: str = Field(index=True, unique=True)
    description: Optional[str] = None
    parent_id: Optional[int] = Field(default=None, foreign_key="category.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Prompt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    body: str
    category_id: int = Field(foreign_key="category.id")
    subcategory_id: Optional[int] = Field(default=None, foreign_key="category.id")
    ai_platform: Optional[str] = None
    instructions: Optional[str] = None
    tags: Optional[str] = None  # JSON string for simplicity in v1
    status: str = Field(default="published")  # 'draft' | 'published' | 'archived'
    created_by: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class PromptSubmission(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    body: str
    category_id: int = Field(foreign_key="category.id")
    subcategory_id: Optional[int] = Field(default=None, foreign_key="category.id")
    ai_platform: Optional[str] = None
    instructions: Optional[str] = None
    tags: Optional[str] = None
    status: str = Field(default="pending")  # 'pending' | 'approved' | 'rejected'
    submitted_by: Optional[int] = Field(default=None, foreign_key="user.id")
    reviewer_notes: Optional[str] = None
    approved_prompt_id: Optional[int] = Field(default=None, foreign_key="prompt.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: int = Field(foreign_key="user.id")
    action: str  # CREATE_PROMPT, UPDATE_PROMPT, APPROVE_SUBMISSION, etc.
    payload: str  # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)