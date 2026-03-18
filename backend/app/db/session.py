"""数据库会话与 SQLAlchemy 基类定义。"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """所有 ORM 模型的共同父类。"""


settings = get_settings()
# `pool_pre_ping=True` 可以在取出连接时先做一次探活，减少长连接失效问题。
engine = create_engine(settings.mysql_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator:
    """FastAPI 依赖注入使用的数据库会话工厂。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
