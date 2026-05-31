"""
Qdrant 向量操作（替换原 ChromaDB）

支持：
  - 本地 Embedding（bge-small-zh-v1.5，通过 sentence-transformers）
  - 智谱 API Embedding（fallback）
  - ENABLE_VECTOR 开关
Qdrant 不可用时优雅降级。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# import shared schema
_SHARED_DIR = str(Path(__file__).resolve().parents[2] / "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)
from schema import IngestPayload  # noqa: E402


def _get_zhipu_embedding(texts: List[str], api_key: str) -> Optional[List[List[float]]]:
    """调用智谱 embedding API，失败返回 None。"""
    if not api_key:
        return None
    try:
        import zhipuai
        client = zhipuai.ZhipuAI(api_key=api_key)
        resp = client.embeddings.create(
            model="embedding-3",
            input=texts,
        )
        return [item.embedding for item in resp.data]
    except Exception as e:
        logger.warning("智谱 embedding API failed: %s", e)
        return None


class VectorService:
    def __init__(
        self,
        enabled: bool = True,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        collection_name: str = "video2kb",
        zai_api_key: str = "",
        embedding_provider: str = "local",
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
    ):
        """
        enabled: ENABLE_VECTOR 开关
        qdrant_host/port: Qdrant 服务地址
        collection_name: Qdrant collection 名称
        zai_api_key: 智谱 API key（fallback embedding）
        embedding_provider: local | zhipu
        embedding_model: 本地模型名或智谱模型名
        """
        self._enabled = enabled
        self._zai_api_key = zai_api_key
        self._embedding_provider = embedding_provider
        self._embedding_model = embedding_model
        self._collection_name = collection_name
        self._available = False
        self._client = None
        self._local_embedder = None
        self._embedding_dim = 512  # bge-small-zh-v1.5 默认维度

        if not enabled:
            logger.info("VectorService: DISABLED by ENABLE_VECTOR=false")
            return

        # 初始化本地 embedder
        if embedding_provider == "local":
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("VectorService: loading local model %s ...", embedding_model)
                self._local_embedder = SentenceTransformer(embedding_model)
                self._embedding_dim = self._local_embedder.get_sentence_embedding_dimension()
                logger.info("VectorService: local model loaded, dim=%d", self._embedding_dim)
            except Exception as e:
                logger.warning("VectorService: local model load failed: %s", e)
                logger.info("VectorService: falling back to zhipu embedding")
                self._embedding_provider = "zhipu"

        # 连接 Qdrant
        try:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(host=qdrant_host, port=qdrant_port)

            # 确保 collection 存在
            from qdrant_client.models import Distance, VectorParams
            collections = [c.name for c in self._client.get_collections().collections]
            if collection_name not in collections:
                self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=self._embedding_dim, distance=Distance.COSINE),
                )
                logger.info("VectorService: created collection '%s' (dim=%d)", collection_name, self._embedding_dim)
            else:
                logger.info("VectorService: using existing collection '%s'", collection_name)

            self._available = True
            logger.info("VectorService: Qdrant connected at %s:%d", qdrant_host, qdrant_port)
        except ImportError:
            logger.warning("VectorService: qdrant-client not installed, vector disabled")
        except Exception as e:
            logger.warning("VectorService: Qdrant connection failed: %s", e)

    @property
    def available(self) -> bool:
        return self._enabled and self._available

    def _compute_embeddings(self, texts: List[str]) -> List[List[float]]:
        """计算文本 embedding，优先本地，fallback 智谱"""
        # 1) 尝试本地 embedding
        if self._local_embedder is not None:
            try:
                embeddings = self._local_embedder.encode(texts, normalize_embeddings=True)
                return [e.tolist() for e in embeddings]
            except Exception as e:
                logger.warning("VectorService: local embedding failed: %s", e)

        # 2) 尝试智谱 API
        if self._zai_api_key:
            result = _get_zhipu_embedding(texts, self._zai_api_key)
            if result is not None:
                logger.debug("VectorService: used 智谱 embedding for %d texts", len(texts))
                return result

        raise RuntimeError("No embedding method available (local model failed + zhipu API unavailable)")

    # ── Ingest ────────────────────────────────────────────────────────

    def ingest(self, payload: IngestPayload) -> int:
        """向 Qdrant 写入文档。返回存入的文档数量。"""
        if not self.available:
            logger.warning("VectorService.ingest: not available, skipping")
            return 0

        from qdrant_client.models import PointStruct

        video_url = payload.video.url
        video_title = payload.video.title
        # 第三波新增：存储路径
        audio_storage_id = payload.audio_storage_id or ""
        transcript_storage_id = payload.transcript_storage_id or ""
        audio_storage_path = payload.audio_storage_path or ""

        docs = []
        metadatas = []
        ids = []

        # 1) transcript 全文
        if payload.transcript.strip():
            docs.append(payload.transcript)
            metadatas.append({
                "video_url": video_url, "type": "transcript", "title": video_title,
                "audio_storage_id": audio_storage_id,
                "transcript_storage_id": transcript_storage_id,
            })
            ids.append(f"transcript_{video_url}")

        # 2) summary
        if payload.summary.full_summary.strip():
            docs.append(payload.summary.full_summary)
            metadatas.append({
                "video_url": video_url, "type": "summary", "title": video_title,
                "audio_storage_id": audio_storage_id,
                "transcript_storage_id": transcript_storage_id,
            })
            ids.append(f"summary_{video_url}")

        # 3) 每个 entity 的 description
        for i, ent in enumerate(payload.entities):
            text = f"{ent.name}: {ent.description}".strip()
            if text and text != ent.name + ": ":
                docs.append(text)
                metadatas.append({
                    "video_url": video_url,
                    "entity_name": ent.name,
                    "entity_type": ent.type,
                    "type": "entity",
                    "confidence": ent.confidence,
                    "title": video_title,
                })
                ids.append(f"entity_{video_url}_{i}_{ent.name}")

        if not docs:
            logger.info("VectorService.ingest: no documents to store for %s", video_url)
            return 0

        # 计算 embeddings
        try:
            embeddings = self._compute_embeddings(docs)
        except Exception as e:
            logger.error("VectorService.ingest: embedding computation failed: %s", e)
            return 0

        # 构建 Qdrant Points（用 id hash 作为 uint64）
        import hashlib
        points = []
        for i, (doc_id, embedding, metadata) in enumerate(zip(ids, embeddings, metadatas)):
            point_id = int(hashlib.md5(doc_id.encode()).hexdigest()[:16], 16)
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={"id": doc_id, **metadata},
                )
            )

        try:
            self._client.upsert(
                collection_name=self._collection_name,
                points=points,
            )
            logger.info("VectorService.ingest: stored %d docs for %s", len(docs), video_url)
            return len(docs)
        except Exception as e:
            logger.error("VectorService.ingest error: %s", e)
            return 0

    # ── Search ────────────────────────────────────────────────────────

    def search(self, query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """语义搜索：向量化查询文本 → Qdrant cosine similarity。"""
        if not self.available:
            return [{"error": "vector_unavailable", "message": "Vector DB is not connected"}]

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        try:
            query_vector = self._compute_embeddings([query_text])[0]

            results = self._client.search(
                collection_name=self._collection_name,
                query_vector=query_vector,
                limit=top_k,
            )

            hits = []
            for result in results:
                hit = {
                    "id": result.payload.get("id", str(result.id)),
                    "document": result.payload.get("text", ""),
                    "metadata": {k: v for k, v in result.payload.items() if k != "text"},
                    "score": result.score,
                }
                hits.append(hit)

            return hits
        except Exception as e:
            logger.error("VectorService.search error: %s", e)
            return [{"error": "search_failed", "message": str(e)}]
