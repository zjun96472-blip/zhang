"""应用配置模块。

这里集中定义后端服务运行时所需的环境变量，并把它们转换成
代码里更易使用的 Python 类型。
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """统一管理 ShopMate 后端配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # 关闭自动 JSON 解码，避免像 CORS_ORIGINS 这样的简单字符串被误判为 JSON。
        enable_decoding=False,
    )

    app_name: str = "ShopMate"
    api_prefix: str = "/api"
    mysql_url: str = "mysql+pymysql://shopmate:shopmate@mysql:3306/shopmate"
    redis_url: str = "redis://redis:6379/0"
    milvus_uri: str = "http://milvus:19530"
    milvus_token: str = ""
    milvus_collection: str = "shopmate_kb"
    dashscope_api_key: str = "sk-c8c111d12124466499f0b4b81e74c636"
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3-max"
    embedding_model: str = "text-embedding-v4"
    embedding_dimensions: int = 1024
    memory_ttl_seconds: int = 86400
    chat_history_window: int = 10
    use_mock_llm: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    auth_secret_key: str = "shopmate-dev-secret-key-please-change-2026"
    auth_algorithm: str = "HS256"
    auth_cookie_name: str = "shopmate_access_token"
    access_token_ttl_seconds: int = 604800
    auth_cookie_secure: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: str | list[str]) -> list[str]:
        """把逗号分隔的 CORS 字符串转换为列表。"""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """缓存配置对象，避免每次依赖注入都重新读取环境变量。"""
    return Settings()
