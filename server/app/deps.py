"""
依赖注入 — 管理 Neo4j driver 和 ChromaDB client 的生命周期
"""
from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# 全局单例，在 main.py 的 lifespan 中初始化
_neo4j_driver = None
_chroma_client = None


def get_neo4j_driver():
    """获取 Neo4j driver（可能为 None）"""
    return _neo4j_driver


def get_chroma_client():
    """获取 ChromaDB client（可能为 None）"""
    return _chroma_client


def set_neo4j_driver(driver):
    global _neo4j_driver
    _neo4j_driver = driver


def set_chroma_client(client):
    global _chroma_client
    _chroma_client = client


def clear_all():
    global _neo4j_driver, _chroma_client
    if _neo4j_driver:
        try:
            _neo4j_driver.close()
        except Exception:
            pass
        _neo4j_driver = None
    _chroma_client = None
