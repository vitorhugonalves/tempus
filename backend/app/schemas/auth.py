from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: UserRole

    model_config = {"from_attributes": True}
