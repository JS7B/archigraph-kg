"""应用配置：从仓库根 .env 读取，全部走环境变量，零硬编码密钥/地址/模型名。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 本文件位于 backend/app/config.py，仓库根为其上三级目录。
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    """应用配置项。字段名 snake_case，环境变量名大小写不敏感。"""

    # LLM（OpenAI-compatible）
    openai_base_url: str = ""
    openai_api_key: str = ""
    chat_model: str = ""
    embedding_model: str = ""
    embedding_dim: int = 3072
    rerank_model: str = "bge-reranker-v2-m3"

    # Neo4j
    neo4j_uri: str = ""
    neo4j_username: str = ""
    neo4j_password: str = ""

    # 文档上传
    max_upload_mb: int = 10

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """获取全局唯一配置实例（带缓存，避免重复读取 .env）。"""
    return Settings()
