from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field, EmailStr


class UserRole(str, Enum):
    ADMIN = "admin"
    INVESTIGATOR = "investigator"
    WITNESS = "witness"


class User(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    email: EmailStr
    hashed_password: str
    full_name: str
    role: UserRole = UserRole.INVESTIGATOR
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}