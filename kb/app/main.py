"""
Video2KB Knowledge Base — 数据服务 FastAPI 入口
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("kb")


# ── Lifespan (startup / shutdown) ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────
    logger.info("Starting KB Data Service...")

    # ── Memgraph（原 Neo4j）───────────────────────────────────────
    from app.services.graph_service import GraphService
    graph_service = GraphService(
        enabled=settings.ENABLE_GRAPH,
        uri=settings.MEMGRAPH_URI,
        username=settings.MEMGRAPH_USER,
        password=settings.MEMGRAPH_PASSWORD,
    )
    app.state.graph_service = graph_service

    # ── Qdrant（原 ChromaDB）───────────────────────────────────────
    from app.services.vector_service import VectorService
    vector_service = VectorService(
        enabled=settings.ENABLE_VECTOR,
        qdrant_host=settings.QDRANT_HOST,
        qdrant_port=settings.QDRANT_PORT,
        collection_name=settings.QDRANT_COLLECTION,
        zai_api_key=settings.ZAI_API_KEY,
        embedding_provider=settings.EMBEDDING_PROVIDER,
        embedding_model=settings.EMBEDDING_MODEL,
    )
    app.state.vector_service = vector_service

    # ── LlamaIndex RAG ───────────────────────────────────────────
    from app.services.llamaindex_service import LlamaIndexService
    llamaindex_service = LlamaIndexService(
        enabled=settings.ENABLE_LLAMAINDEX,
        qdrant_host=settings.QDRANT_HOST,
        qdrant_port=settings.QDRANT_PORT,
        collection_name=settings.QDRANT_COLLECTION,
        zai_api_key=settings.ZAI_API_KEY,
        llm_model=settings.LLM_MODEL,
    )
    app.state.llamaindex_service = llamaindex_service

    logger.info(
        "KB ready — graph: %s, vector: %s, llamaindex: %s",
        "✅" if graph_service.available else "❌",
        "✅" if vector_service.available else "❌",
        "✅" if llamaindex_service.available else "❌",
    )

    yield

    # ── Shutdown ──────────────────────────────────────────────────
    logger.info("Shutting down KB Data Service...")


# ── App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Video2KB — Knowledge Base",
    description="接收 Pipeline 分析结果，存入 Memgraph + Qdrant，提供查询接口",
    version="0.2.0",
    lifespan=lifespan,
)


# ── API Key 中间件 ────────────────────────────────────────────────────
@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    # 跳过根路由和 docs
    if request.url.path in ("/", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)

    api_key = request.headers.get("X-API-Key", "")
    if api_key != settings.API_KEY:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Invalid or missing X-API-Key"},
        )
    return await call_next(request)


# ── Routers ───────────────────────────────────────────────────────────
from app.routers import ingest, query  # noqa: E402

app.include_router(ingest.router)
app.include_router(query.router)


# ── Root ──────────────────────────────────────────────────────────────
@app.get("/", tags=["status"])
async def root():
    graph_ok = app.state.graph_service.available if hasattr(app.state, "graph_service") else False
    vector_ok = app.state.vector_service.available if hasattr(app.state, "vector_service") else False
    li_ok = app.state.llamaindex_service.available if hasattr(app.state, "llamaindex_service") else False
    return {
        "service": "Video2KB — Knowledge Base",
        "version": "0.2.0",
        "status": {
            "memgraph": "connected" if graph_ok else "unavailable",
            "qdrant": "connected" if vector_ok else "unavailable",
            "llamaindex": "connected" if li_ok else "unavailable",
        },
        "endpoints": {
            "ingest": "POST /api/ingest",
            "query_entity": "GET /api/query/entity?name=xxx",
            "query_video": "GET /api/query/video?url=xxx",
            "search": "POST /api/query/search",
            "ask": "POST /api/query/ask",
            "subgraph": "GET /api/query/subgraph?entity=xxx&depth=2",
        },
    }
