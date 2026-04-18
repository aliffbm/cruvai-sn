from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://cruvai:cruvai@localhost:5432/cruvai_sn"
    database_url_sync: str = "postgresql://cruvai:cruvai@localhost:5432/cruvai_sn"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "change-me-to-a-random-64-char-string"
    cruvai_encryption_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # AI / LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    default_llm_provider: str = "anthropic"
    default_model: str = "claude-sonnet-4-20250514"

    # Application
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    cors_origins: List[str] = ["http://localhost:3000"]
    log_level: str = "INFO"

    # OpenClaw (Phase 2)
    openclaw_enabled: bool = False

    # Storage backend for guidance assets
    storage_backend: str = "filesystem"  # filesystem, minio, s3
    storage_root: str = "/var/lib/cruvai/assets"
    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "cruvai-guidance-assets"
    minio_secure: bool = True

    # Toolkit ingestion
    toolkit_root: str = ""  # e.g. /home/user/.claude

    model_config = {
        "env_file": ["../.env", ".env"],
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
