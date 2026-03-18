"""认证相关接口结构。"""

from pydantic import BaseModel, Field


class UserPayload(BaseModel):
    """返回给前端的用户公开信息。"""

    id: str
    email: str
    display_name: str


class AuthEnvelope(BaseModel):
    """认证接口统一响应结构。"""

    user: UserPayload


class RegisterRequest(BaseModel):
    """注册接口入参。"""

    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=120)


class LoginRequest(BaseModel):
    """登录接口入参。"""

    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
