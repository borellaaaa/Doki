from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime


# ──────────────────────────────────────────────
#  AUTH SCHEMAS
# ──────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("A senha deve conter pelo menos um número.")
        if not any(c.isalpha() for c in v):
            raise ValueError("A senha deve conter pelo menos uma letra.")
        return v


class UserLoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    doki_version: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
#  CHAT SCHEMAS
# ──────────────────────────────────────────────

class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[int] = None


class ChatMessageResponse(BaseModel):
    conversation_id: int
    message_id: int
    response: str
    subject: Optional[str]
    subject_display: Optional[str]
    subject_icon: Optional[str]
    topic: Optional[str]
    confidence: float
    blocked: bool
    sources: list = []
    doki_version: str


# ──────────────────────────────────────────────
#  EXPERTISE SCHEMAS
# ──────────────────────────────────────────────

class ExpertiseItemResponse(BaseModel):
    subject: str
    display_name: str
    icon: str
    score: float
    level: str
    interaction_count: int
    last_studied_at: Optional[str]


class ExpertiseProfileResponse(BaseModel):
    user_id: int
    profile: list[ExpertiseItemResponse]
    total_interactions: int
    top_subject: Optional[str]
    knowledge_summary: dict


# ──────────────────────────────────────────────
#  CONVERSATION SCHEMAS
# ──────────────────────────────────────────────

class ConversationResponse(BaseModel):
    id: int
    title: Optional[str]
    subject: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    subject_detected: Optional[str]
    confidence_score: Optional[float]
    was_blocked: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
#  HEALTH / STATUS SCHEMAS
# ──────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    doki_version: str
    environment: str
    database: str
    vector_store: str
