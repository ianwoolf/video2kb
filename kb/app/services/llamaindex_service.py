"""
LlamaIndex 服务 — 基于 Qdrant 向量索引的 RAG 查询

提供 /api/query/ask 接口，使用 LlamaIndex + Qdrant + 智谱 LLM。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LlamaIndexService:
    def __init__(
        self,
        enabled: bool = True,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        collection_name: str = "video2kb",
        zai_api_key: str = "",
        llm_model: str = "glm-4-flash",
    ):
        """
        enabled: ENABLE_LLAMAINDEX 开关
        qdrant_host/port: Qdrant 服务地址
        collection_name: Qdrant collection（与 VectorService 共用）
        zai_api_key: 智谱 API key
        llm_model: LLM 模型名称
        """
        self._enabled = enabled
        self._available = False
        self._zai_api_key = zai_api_key
        self._llm_model = llm_model
        self._query_engine = None

        if not enabled:
            logger.info("LlamaIndexService: DISABLED by ENABLE_LLAMAINDEX=false")
            return

        try:
            self._init_service(qdrant_host, qdrant_port, collection_name, zai_api_key, llm_model)
        except ImportError as e:
            logger.warning("LlamaIndexService: missing dependency: %s", e)
        except Exception as e:
            logger.warning("LlamaIndexService: init failed: %s", e)

    def _init_service(
        self,
        qdrant_host: str,
        qdrant_port: int,
        collection_name: str,
        zai_api_key: str,
        llm_model: str,
    ):
        """初始化 LlamaIndex + Qdrant + LLM"""
        from qdrant_client import QdrantClient

        # Qdrant client
        qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)

        # 检查 collection 是否有数据
        info = qdrant_client.get_collection(collection_name)
        if info.points_count == 0:
            logger.info("LlamaIndexService: collection '%s' is empty, will work after data ingestion", collection_name)
        else:
            logger.info("LlamaIndexService: collection '%s' has %d points", collection_name, info.points_count)

        # 配置 LlamaIndex
        from llama_index.core import VectorStoreIndex, StorageContext
        from llama_index.vector_stores.qdrant import QdrantVectorStore

        # Qdrant 向量存储
        vector_store = QdrantVectorStore(
            client=qdrant_client,
            collection_name=collection_name,
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # LLM 配置 — 使用智谱通过 OpenAI 兼容接口
        if zai_api_key:
            from llama_index.llms.openai_like import OpenAILike
            llm = OpenAILike(
                model=llm_model,
                api_base="https://open.bigmodel.cn/api/paas/v4",
                api_key=zai_api_key,
                is_chat_model=True,
                temperature=0.1,
                max_tokens=2048,
            )
            from llama_index.core import Settings as LlamaSettings
            LlamaSettings.llm = llm

        # Embedding 配置 — 复用本地 embedding
        try:
            from sentence_transformers import SentenceTransformer
            model_name = "BAAI/bge-small-zh-v1.5"
            st = SentenceTransformer(model_name)
            dim = st.get_sentence_embedding_dimension()

            from llama_index.core.embeddings import BaseEmbedding
            from typing import cast
            from llama_index.core.base.embeddings.base import Embedding

            class LocalBGEEmbedding(BaseEmbedding):
                def __init__(self, model: SentenceTransformer):
                    self._model = model

                def _get_query_embedding(self, query: str) -> list[float]:
                    return cast(list[float], self._model.encode([query], normalize_embeddings=True)[0].tolist())

                def _get_text_embedding(self, text: str) -> list[float]:
                    return cast(list[float], self._model.encode([text], normalize_embeddings=True)[0].tolist())

                async def _aget_query_embedding(self, query: str) -> list[float]:
                    return self._get_query_embedding(query)

                async def _aget_text_embedding(self, text: str) -> list[float]:
                    return self._get_text_embedding(text)

                @property
                def embed_dim(self) -> int:
                    return dim

            from llama_index.core import Settings as LlamaSettings
            LlamaSettings.embed_model = LocalBGEEmbedding(st)
            logger.info("LlamaIndexService: using local BGE embedding (dim=%d)", dim)
        except Exception as e:
            logger.warning("LlamaIndexService: local embedding init failed: %s", e)

        # 创建 Index
        self._index = VectorStoreIndex.from_vector_store(
            vector_store,
            storage_context=storage_context,
        )
        self._query_engine = self._index.as_query_engine(
            similarity_top_k=5,
            response_mode="tree_summarize",
        )

        self._available = True
        logger.info("LlamaIndexService: ready")

    @property
    def available(self) -> bool:
        return self._enabled and self._available

    def ask(self, question: str) -> Dict[str, Any]:
        """
        RAG 查询：基于 Qdrant 向量索引回答问题。

        Returns:
            {"answer": "...", "source_nodes": [...]}
        """
        if not self.available:
            return {
                "error": "llamaindex_unavailable",
                "message": "LlamaIndex service is not available",
            }

        try:
            response = self._query_engine.query(question)
            source_nodes = []
            for node in response.source_nodes:
                source_nodes.append({
                    "text": node.node.get_content()[:200],
                    "metadata": node.node.metadata,
                    "score": node.score,
                })

            return {
                "answer": str(response),
                "source_nodes": source_nodes,
            }
        except Exception as e:
            logger.error("LlamaIndexService.ask error: %s", e)
            return {
                "error": "ask_failed",
                "message": str(e),
            }
