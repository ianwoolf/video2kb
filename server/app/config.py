"""
Part 2 配置管理 — 使用 pydantic-settings 读取环境变量
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── API ────────────────────────────────────────────────────────────
    API_KEY: str = "dev-key"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Neo4j ──────────────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # ── ChromaDB ───────────────────────────────────────────────────────
    CHROMA_DIR: str = "data/chroma"

    # ── 智谱 Embedding ────────────────────────────────────────────────
    ZAI_API_KEY: str = ""


settings = Settings()
