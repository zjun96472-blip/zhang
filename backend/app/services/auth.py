"""认证与登录态管理。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, Request, Response, status
from passlib.context import CryptContext

from app.core.config import Settings
from app.models.entities import User
from app.repositories.store import ShopRepository


class AuthService:
    """负责密码哈希、JWT 签发与 Cookie 写入。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(self, password: str) -> str:
        """把明文密码转成不可逆哈希。"""
        return self.password_context.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """校验用户输入密码是否与数据库哈希匹配。"""
        return self.password_context.verify(password, password_hash)

    def create_access_token(self, user_id: str) -> str:
        """签发访问令牌。"""
        expires_at = datetime.now(UTC) + timedelta(seconds=self.settings.access_token_ttl_seconds)
        payload = {
            "sub": user_id,
            "exp": expires_at,
        }
        return jwt.encode(payload, self.settings.auth_secret_key, algorithm=self.settings.auth_algorithm)

    def decode_access_token(self, token: str) -> str | None:
        """从 JWT 中解析用户主键。"""
        try:
            payload = jwt.decode(
                token,
                self.settings.auth_secret_key,
                algorithms=[self.settings.auth_algorithm],
            )
        except jwt.PyJWTError:
            return None
        return payload.get("sub")

    def set_auth_cookie(self, response: Response, token: str) -> None:
        """将 JWT 写入 HttpOnly Cookie。"""
        response.set_cookie(
            key=self.settings.auth_cookie_name,
            value=token,
            httponly=True,
            samesite="lax",
            secure=self.settings.auth_cookie_secure,
            max_age=self.settings.access_token_ttl_seconds,
            expires=self.settings.access_token_ttl_seconds,
            path="/",
        )

    def clear_auth_cookie(self, response: Response) -> None:
        """清除登录 Cookie。"""
        response.delete_cookie(
            key=self.settings.auth_cookie_name,
            httponly=True,
            samesite="lax",
            secure=self.settings.auth_cookie_secure,
            path="/",
        )

    def get_current_user(self, request: Request, repo: ShopRepository) -> User:
        """从请求 Cookie 中恢复当前登录用户。"""
        token = request.cookies.get(self.settings.auth_cookie_name)
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        user_id = self.decode_access_token(token)
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        user = repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user
