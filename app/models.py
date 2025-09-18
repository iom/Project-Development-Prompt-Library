from typing import Optional, List
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
    ai_platforms: Optional[str] = None  # JSON string storing list of platforms
    instructions: Optional[str] = None
    tags: Optional[str] = None  # JSON string for simplicity in v1
    status: str = Field(default="published")  # 'draft' | 'published' | 'archived'
    created_by: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_platforms(self) -> List[str]:
        """Get list of AI platforms from JSON string"""
        if not self.ai_platforms:
            return []
        try:
            return json.loads(self.ai_platforms)
        except (json.JSONDecodeError, TypeError):
            # Handle legacy single platform or malformed data
            return [self.ai_platforms] if self.ai_platforms else []
    
    def set_platforms(self, platforms: List[str]):
        """Set AI platforms as JSON string"""
        if platforms:
            self.ai_platforms = json.dumps(platforms)
        else:
            self.ai_platforms = None
    
    # Legacy property for backward compatibility
    @property
    def ai_platform(self) -> Optional[str]:
        """Return first platform for backward compatibility"""
        platforms = self.get_platforms()
        return platforms[0] if platforms else None

class PromptSubmission(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    body: str
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")
    subcategory_id: Optional[int] = Field(default=None, foreign_key="category.id")
    ai_platforms: Optional[str] = None  # JSON string storing list of platforms
    instructions: Optional[str] = None
    tags: Optional[str] = None
    suggested_category_name: Optional[str] = None  # For new category suggestions
    status: str = Field(default="pending")  # 'pending' | 'approved' | 'rejected'
    submitted_by: Optional[int] = Field(default=None, foreign_key="user.id")
    reviewer_notes: Optional[str] = None
    approved_prompt_id: Optional[int] = Field(default=None, foreign_key="prompt.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None

    def get_platforms(self) -> List[str]:
        """Get list of AI platforms from JSON string"""
        if not self.ai_platforms:
            return []
        try:
            return json.loads(self.ai_platforms)
        except (json.JSONDecodeError, TypeError):
            # Handle legacy single platform or malformed data
            return [self.ai_platforms] if self.ai_platforms else []
    
    def set_platforms(self, platforms: List[str]):
        """Set AI platforms as JSON string"""
        if platforms:
            self.ai_platforms = json.dumps(platforms)
        else:
            self.ai_platforms = None
    
    # Legacy property for backward compatibility
    @property
    def ai_platform(self) -> Optional[str]:
        """Return first platform for backward compatibility"""
        platforms = self.get_platforms()
        return platforms[0] if platforms else None

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: int = Field(foreign_key="user.id")
    action: str  # CREATE_PROMPT, UPDATE_PROMPT, APPROVE_SUBMISSION, etc.
    payload: str  # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)