"""
ChromaDB 向量操作

支持：
  - 智谱 API Embedding（默认，云端调用）
  - 本地 Embedding（bge-small-zh-v1.5，通过 sentence-transformers，可选）
  - ENABLE_VECTOR 开关
ChromaDB 不可用时优雅降级。

ChromaDB 为纯 Python 嵌入式方案，不需要独立 Docker 服务，ARM64 兼容。
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
        chroma_dir: str = "data/chroma",
        collection_name: str = "video2kb",
        zai_api_key: str = "",
        embedding_provider: str = "zhipu",
        embedding_model: str = "embedding-3",
    ):
        """
        enabled: ENABLE_VECTOR 开关
        chroma_dir: ChromaDB 持久化目录
        collection_name: ChromaDB collection 名称
        zai_api_key: 智谱 API key
        embedding_provider: zhipu（默认，云端） | local（本地 bge 模型）
        embedding_model: 智谱模型名 或 本地模型名
        """
        self._enabled = enabled
        self._zai_api_key = zai_api_key
        self._embedding_provider = embedding_provider
        self._embedding_model = embedding_model
        self._collection_name = collection_name
        self._available = False
        self._client = None
        self._collection = None
        self._local_embedder = None

        if not enabled:
            logger.info("VectorService: DISABLED by ENABLE_VECTOR=false")
            return

        # 初始化本地 embedder（仅当 embedding_provider=local 时）
        if embedding_provider == "local":
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("VectorService: loading local model %s ...", embedding_model)
                self._local_embedder = SentenceTransformer(embedding_model)
                dim = self._local_embedder.get_sentence_embedding_dimension()
                logger.info("VectorService: local model loaded, dim=%d", dim)
            except Exception as e:
                logger.warning("VectorService: local model load failed: %s", e)
                logger.info("VectorService: falling back to zhipu embedding")
                self._embedding_provider = "zhipu"

        # 初始化 ChromaDB
        try:
            import chromadb
            chroma_path = Path(chroma_dir)
            chroma_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(chroma_path))
            self._collection = self._client.get_or_create_collection(
                name=collection_name,
            )
            self._available = True
            logger.info("VectorService: ChromaDB ready at %s (collection='%s')", chroma_dir, collection_name)
        except ImportError:
            logger.warning("VectorService: chromadb not installed, vector disabled")
        except Exception as e:
            logger.warning("VectorService: ChromaDB init failed: %s", e)

    @property
    def available(self) -> bool:
        return self._enabled and self._available

    def _compute_embeddings(self, texts: List[str]) -> List[List[float]]:
        """计算文本 embedding"""
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
        """向 ChromaDB 写入文档。返回存入的文档数量。"""
        if not self.available:
            logger.warning("VectorService.ingest: not available, skipping")
            return 0

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

        # 写入 ChromaDB
        try:
            # ChromaDB 需要的 id 格式：字符串
            chroma_ids = ids
            self._collection.upsert(
                ids=chroma_ids,
                documents=docs,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            logger.info("VectorService.ingest: stored %d docs for %s", len(docs), video_url)
            return len(docs)
        except Exception as e:
            logger.error("VectorService.ingest error: %s", e)
            return 0

    # ── Search ────────────────────────────────────────────────────────

    def search(self, query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """语义搜索：向量化查询文本 → ChromaDB cosine similarity。"""
        if not self.available:
            return [{"error": "vector_unavailable", "message": "Vector DB is not connected"}]

        try:
            query_embedding = self._compute_embeddings([query_text])[0]

            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, self._collection.count() or 1),
            )

            hits = []
            if results and results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    doc_id = results["ids"][0][i]
                    metadata = results["metadatas"][0][i] if results["metadatas"] and results["metadatas"][0] else {}
                    document = results["documents"][0][i] if results["documents"] and results["documents"][0] else ""
                    distance = results["distances"][0][i] if results["distances"] and results["distances"][0] else 0
                    score = 1.0 - distance  # ChromaDB 返回距离，转为相似度
                    hits.append({
                        "id": doc_id,
                        "document": document,
                        "metadata": metadata,
                        "score": score,
                    })

            return hits
        except Exception as e:
            logger.error("VectorService.search error: %s", e)
            return [{"error": "search_failed", "message": str(e)}]
