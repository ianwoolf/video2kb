"""
Part 2 FastAPI 入口 — Video2KB 数据服务
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
logger = logging.getLogger("part2")


# ── Lifespan (startup / shutdown) ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────
    logger.info("Starting Part 2 Data Service...")

    # Neo4j
    graph_service = None
    try:
        from neo4j import GraphDatabase
        from app.services.graph_service import GraphService
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        graph_service = GraphService(driver=driver)
    except Exception as e:
        logger.warning("Neo4j unavailable (service will start without graph): %s", e)
        from app.services.graph_service import GraphService
        graph_service = GraphService(driver=None)

    app.state.graph_service = graph_service

    # ChromaDB
    vector_service = None
    try:
        import chromadb
        from app.services.vector_service import VectorService
        chroma_dir = Path(settings.CHROMA_DIR)
        chroma_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(chroma_dir))
        vector_service = VectorService(chroma_client=client, zai_api_key=settings.ZAI_API_KEY)
    except Exception as e:
        logger.warning("ChromaDB unavailable (service will start without vector): %s", e)
        from app.services.vector_service import VectorService
        vector_service = VectorService(chroma_client=None, zai_api_key=settings.ZAI_API_KEY)

    app.state.vector_service = vector_service

    logger.info(
        "Part 2 ready — graph: %s, vector: %s",
        "✅" if graph_service.available else "❌",
        "✅" if vector_service.available else "❌",
    )

    yield

    # ── Shutdown ──────────────────────────────────────────────────
    logger.info("Shutting down Part 2 Data Service...")
    if graph_service and hasattr(graph_service, "_driver") and graph_service._driver:
        try:
            graph_service._driver.close()
        except Exception:
            pass


# ── App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Video2KB Part 2 — Data Service",
    description="接收 Part 1 分析结果，存入 Neo4j + ChromaDB，提供查询接口",
    version="0.1.0",
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
    return {
        "service": "Video2KB Part 2 — Data Service",
        "version": "0.1.0",
        "status": {
            "neo4j": "connected" if graph_ok else "unavailable",
            "chromadb": "connected" if vector_ok else "unavailable",
        },
        "endpoints": {
            "ingest": "POST /api/ingest",
            "query_entity": "GET /api/query/entity?name=xxx",
            "query_video": "GET /api/query/video?url=xxx",
            "search": "POST /api/query/search",
            "subgraph": "GET /api/query/subgraph?entity=xxx&depth=2",
        },
    }
