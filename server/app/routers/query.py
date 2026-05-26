"""
GET/POST /api/query/* — 实体查询、语义搜索、子图遍历
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app.models import ApiResponse, SearchQuery

logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


async def _get_services(request: Request):
    graph_svc = request.app.state.graph_service
    vector_svc = request.app.state.vector_service
    return graph_svc, vector_svc


# ── GET /api/query/entity?name=xxx ────────────────────────────────────

@router.get("/api/query/entity")
async def query_entity(name: str = Query(..., description="实体名称"), request: Request = None):
    graph_svc, _ = await _get_services(request)

    if not graph_svc.available:
        return ApiResponse(status="error", message="Neo4j is not available")

    try:
        result = graph_svc.query_entity(name)
        return ApiResponse(status="ok", data=result, message=f"Found {len(result)} relations for '{name}'")
    except Exception as e:
        logger.error("query_entity error: %s", e)
        return ApiResponse(status="error", message=str(e))


# ── GET /api/query/video?url=xxx ──────────────────────────────────────

@router.get("/api/query/video")
async def query_video(url: str = Query(..., description="视频 URL"), request: Request = None):
    graph_svc, _ = await _get_services(request)

    if not graph_svc.available:
        return ApiResponse(status="error", message="Neo4j is not available")

    try:
        result = graph_svc.query_video(url)
        return ApiResponse(status="ok", data=result, message=f"Found {len(result)} entities for video")
    except Exception as e:
        logger.error("query_video error: %s", e)
        return ApiResponse(status="error", message=str(e))


# ── POST /api/query/search — 语义搜索 ─────────────────────────────────

@router.post("/api/query/search")
async def search(body: SearchQuery, request: Request = None):
    _, vector_svc = await _get_services(request)

    if not vector_svc.available:
        return ApiResponse(status="error", message="ChromaDB is not available")

    try:
        results = vector_svc.search(body.query_text, top_k=body.top_k)
        return ApiResponse(status="ok", data=results, message=f"Found {len(results)} results")
    except Exception as e:
        logger.error("search error: %s", e)
        return ApiResponse(status="error", message=str(e))


# ── GET /api/query/subgraph?entity=xxx&depth=2 ───────────────────────

@router.get("/api/query/subgraph")
async def query_subgraph(
    entity: str = Query(..., description="起始实体名称"),
    depth: int = Query(2, ge=1, le=5, description="遍历深度"),
    request: Request = None,
):
    graph_svc, _ = await _get_services(request)

    if not graph_svc.available:
        return ApiResponse(status="error", message="Neo4j is not available")

    try:
        result = graph_svc.query_subgraph(entity, depth=depth)
        return ApiResponse(status="ok", data=result, message="Subgraph traversal complete")
    except Exception as e:
        logger.error("query_subgraph error: %s", e)
        return ApiResponse(status="error", message=str(e))
