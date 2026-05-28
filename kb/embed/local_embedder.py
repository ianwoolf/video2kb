"""
本地 Embedding 模块 — 基于 sentence-transformers

默认模型: BAAI/bge-small-zh-v1.5 (中文，512 维)
支持手动切换模型。

使用方式:
    from embed.local_embedder import get_embedder

    embedder = get_embedder()
    embeddings = embedder.encode(["你好世界", "测试文本"])
"""
from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# 全局 embedder 实例（懒加载）
_embedder = None
_current_model: Optional[str] = None


def get_embedder(model_name: str = "BAAI/bge-small-zh-v1.5"):
    """获取或创建 embedder（单例模式）"""
    global _embedder, _current_model

    if _embedder is not None and _current_model == model_name:
        return _embedder

    logger.info("加载本地 embedding 模型: %s", model_name)
    from sentence_transformers import SentenceTransformer
    _embedder = SentenceTransformer(model_name)
    _current_model = model_name
    dim = _embedder.get_sentence_embedding_dimension()
    logger.info("本地模型加载完成: %s (dim=%d)", model_name, dim)
    return _embedder


def encode(
    texts: List[str],
    model_name: str = "BAAI/bge-small-zh-v1.5",
    normalize: bool = True,
) -> List[List[float]]:
    """
    对文本列表计算 embedding。

    Args:
        texts: 文本列表
        model_name: 模型名称
        normalize: 是否归一化（推荐 cosine similarity 时开启）

    Returns:
        embedding 列表
    """
    embedder = get_embedder(model_name)
    embeddings = embedder.encode(texts, normalize_embeddings=normalize)
    return [e.tolist() for e in embeddings]


def get_dimension(model_name: str = "BAAI/bge-small-zh-v1.5") -> int:
    """获取模型的 embedding 维度"""
    embedder = get_embedder(model_name)
    return embedder.get_sentence_embedding_dimension()
