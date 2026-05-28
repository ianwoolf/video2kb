"""
Server 配置管理 — 使用 pydantic-settings 读取环境变量
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

    # ── Memgraph (原 Neo4j) ────────────────────────────────────────────
    ENABLE_GRAPH: bool = True
    MEMGRAPH_URI: str = "bolt://localhost:7687"
    MEMGRAPH_USER: str = ""
    MEMGRAPH_PASSWORD: str = ""
    # 保留旧变量兼容（内部不使用）
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = ""
    NEO4J_PASSWORD: str = ""

    # ── Qdrant (原 ChromaDB) ───────────────────────────────────────────
    ENABLE_VECTOR: bool = True
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "video2kb"
    # 保留旧变量兼容
    CHROMA_DIR: str = "data/chroma"

    # ── Embedding ──────────────────────────────────────────────────────
    ZAI_API_KEY: str = ""
    EMBEDDING_PROVIDER: str = "local"  # local | zhipu
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"

    # ── LlamaIndex ─────────────────────────────────────────────────────
    ENABLE_LLAMAINDEX: bool = True
    LLM_PROVIDER: str = "zhipu"
    LLM_MODEL: str = "glm-4-flash"


settings = Settings()
