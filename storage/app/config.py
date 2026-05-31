"""
Storage Service — 物料存储服务配置
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── API ──
    API_KEY: str = "dev-key"
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # ── Storage Backend ──
    STORAGE_BACKEND: str = "local"               # local | s3
    STORAGE_BASE_DIR: str = "data/storage"        # 本地文件系统存储根目录

    # ── S3 / MinIO（当 STORAGE_BACKEND=s3 时使用）──
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_BUCKET: str = "video2kb"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"


settings = Settings()
