"""
Storage Service — 物料存储服务 FastAPI 入口

接收文件上传，持久化存储，提供下载/查询/删除接口。
支持 StorageBackend 抽象接口，默认本地文件系统，可切换 S3/MinIO。
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("storage")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Storage Service...")

    # 根据配置创建存储后端
    if settings.STORAGE_BACKEND == "local":
        from storage.backends.local import LocalStorageBackend
        backend = LocalStorageBackend(base_dir=settings.STORAGE_BASE_DIR)
    elif settings.STORAGE_BACKEND == "s3":
        from storage.backends.local import S3StorageBackend
        backend = S3StorageBackend(
            endpoint=settings.S3_ENDPOINT,
            bucket=settings.S3_BUCKET,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            region=settings.S3_REGION,
        )
    else:
        raise ValueError(f"Unknown STORAGE_BACKEND: {settings.STORAGE_BACKEND}")

    app.state.storage_backend = backend
    logger.info("Storage Service ready — backend=%s", settings.STORAGE_BACKEND)

    yield

    logger.info("Shutting down Storage Service...")


app = FastAPI(
    title="Video2KB — Storage Service",
    description="物料存储服务：上传、下载、查询、删除文件",
    version="0.1.0",
    lifespan=lifespan,
)


# ── API Key 中间件 ──
@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if request.url.path in ("/", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)

    api_key = request.headers.get("X-API-Key", "")
    if api_key != settings.API_KEY:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Invalid or missing X-API-Key"},
        )
    return await call_next(request)


# ── Routers ──
from app.routers import files  # noqa: E402

app.include_router(files.router)


# ── Root ──
@app.get("/", tags=["status"])
async def root():
    return {
        "service": "Video2KB — Storage Service",
        "version": "0.1.0",
        "backend": settings.STORAGE_BACKEND,
        "base_dir": settings.STORAGE_BASE_DIR,
        "endpoints": {
            "upload": "POST /api/upload",
            "download": "GET /api/files/{storage_id}",
            "info": "GET /api/files/{storage_id}/info",
            "delete": "DELETE /api/files/{storage_id}",
            "list": "GET /api/files?prefix=audio&limit=100",
        },
    }
