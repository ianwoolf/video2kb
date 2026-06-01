"""
Transcoder Service — 音频解码服务配置
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── API ──
    API_KEY: str = "dev-key"
    HOST: str = "0.0.0.0"
    PORT: int = 8002

    # ── Storage Service ──
    STORAGE_URL: str = "http://localhost:8001"
    STORAGE_API_KEY: str = ""

    # ── Whisper ASR ──
    WHISPER_MODEL: str = "base"
    WHISPER_LANGUAGE: str = "zh"
    WHISPER_DEVICE: str = "auto"     # auto | cpu | cuda

    # ── Task Queue ──
    TASK_QUEUE: str = "memory"       # memory | redis(未来)
    MAX_CONCURRENT_TASKS: int = 1     # 内存队列最大并发数


settings = Settings()
