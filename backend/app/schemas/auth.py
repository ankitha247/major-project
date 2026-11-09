from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.WITNESS


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    full_name: str


class UserOut(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str