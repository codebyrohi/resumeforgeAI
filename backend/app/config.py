from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from env vars (or a .env file locally) - never from source."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "mysql+pymysql://resume:resume@localhost:3306/resume_builder"

    jwt_secret: str = "dev-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7

    groq_api_key: str = ""
    groq_primary_model: str = "openai/gpt-oss-20b"
    groq_fallback_model: str = "openai/gpt-oss-120b"

    storage_backend: Literal["s3", "local"] = "local"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_public_base_url: str = ""
    local_storage_dir: str = "local_storage"

    public_api_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173"

    max_resume_bytes: int = 5 * 1024 * 1024
    max_photo_bytes: int = 3 * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
