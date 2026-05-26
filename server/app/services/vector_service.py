"""
ChromaDB 向量操作 — 持久化存储 + 智谱 Embedding
Embedding 方案：优先智谱 API，fallback 到 ChromaDB 默认 embedding function。
ChromaDB 不可用时优雅降级。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# import shared schema
_SHARED_DIR = str(Path(__file__).resolve().parents[2] / "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)
from schema import IngestPayload  # noqa: E402

_COLLECTION_NAME = "video2kb"


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
    def __init__(self, chroma_client=None, zai_api_key: str = ""):
        self._client = chroma_client
        self._zai_api_key = zai_api_key
        self._collection = None
        self._available = False

        if chroma_client is not None:
            try:
                self._collection = chroma_client.get_or_create_collection(
                    name=_COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
                self._available = True
                logger.info("VectorService: ChromaDB connected, collection '%s'", _COLLECTION_NAME)
            except Exception as e:
                logger.warning("VectorService: ChromaDB init failed: %s", e)
                self._client = None

    @property
    def available(self) -> bool:
        return self._available

    def _compute_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """尝试智谱 API，fallback 返回 None（让 ChromaDB 用默认 embedding）。"""
        result = _get_zhipu_embedding(texts, self._zai_api_key)
        if result is not None:
            logger.debug("VectorService: used 智谱 embedding for %d texts", len(texts))
        return result

    # ── Ingest ────────────────────────────────────────────────────────

    def ingest(self, payload: IngestPayload) -> int:
        """向 ChromaDB 写入文档。返回存入的文档数量。"""
        if not self._available:
            logger.warning("VectorService.ingest: ChromaDB not available, skipping")
            return 0

        video_url = payload.video.url
        video_title = payload.video.title

        docs = []
        metadatas = []
        ids = []

        # 1) transcript 全文
        if payload.transcript.strip():
            docs.append(payload.transcript)
            metadatas.append({"video_url": video_url, "type": "transcript", "title": video_title})
            ids.append(f"transcript_{video_url}")

        # 2) summary
        if payload.summary.full_summary.strip():
            docs.append(payload.summary.full_summary)
            metadatas.append({"video_url": video_url, "type": "summary", "title": video_title})
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

        # 尝试智谱 embedding
        embeddings = self._compute_embeddings(docs)

        try:
            kwargs: Dict[str, Any] = {
                "documents": docs,
                "metadatas": metadatas,
                "ids": ids,
            }
            if embeddings is not None:
                kwargs["embeddings"] = embeddings

            self._collection.add(**kwargs)
            logger.info("VectorService.ingest: stored %d docs for %s", len(docs), video_url)
            return len(docs)
        except Exception as e:
            logger.error("VectorService.ingest error: %s", e)
            return 0

    # ── Search ────────────────────────────────────────────────────────

    def search(self, query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """语义搜索：向量化查询文本 → ChromaDB cosine similarity。"""
        if not self._available:
            return [{"error": "chromadb_unavailable", "message": "ChromaDB is not connected"}]

        try:
            # 尝试智谱 embedding
            query_embeddings = self._compute_embeddings([query_text])

            kwargs: Dict[str, Any] = {
                "query_texts": [query_text],
                "n_results": min(top_k, self._collection.count() or 1),
            }
            if query_embeddings is not None:
                kwargs["query_embeddings"] = query_embeddings
                # 有自定义 embedding 时不需要 query_texts
                kwargs.pop("query_texts")

            results = self._collection.query(**kwargs)

            # 组装返回
            hits = []
            ids = results.get("ids", [[]])[0]
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for i, doc_id in enumerate(ids):
                hit = {
                    "id": doc_id,
                    "document": documents[i] if i < len(documents) else "",
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distances[i] if i < len(distances) else None,
                }
                hits.append(hit)

            return hits
        except Exception as e:
            logger.error("VectorService.search error: %s", e)
            return [{"error": "search_failed", "message": str(e)}]
