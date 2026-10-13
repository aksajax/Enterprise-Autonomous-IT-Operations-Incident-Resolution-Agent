
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    role: UserRole
    is_active: bool
