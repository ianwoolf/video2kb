"""
POST /api/ingest — 接收 IngestPayload，写入 Neo4j + ChromaDB
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from app.models import IngestPayload, IngestResponse, ApiResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ingest"])


async def _get_services(request: Request):
    """从 app state 获取 service 实例"""
    graph_svc = request.app.state.graph_service
    vector_svc = request.app.state.vector_service
    return graph_svc, vector_svc


@router.post("/api/ingest", response_model=IngestResponse)
async def ingest(payload: IngestPayload, request: Request):
    graph_svc, vector_svc = await _get_services(request)

    video_url = payload.video.url

    # 1) Neo4j
    entities_stored = 0
    relations_stored = 0
    try:
        if graph_svc.available:
            result = graph_svc.ingest(payload)
            entities_stored = result.get("entities_stored", 0)
            relations_stored = result.get("relations_stored", 0)
        else:
            logger.warning("Ingest: graph service not available, skipping Neo4j")
    except Exception as e:
        logger.error("Ingest: graph_service.ingest failed: %s", e)

    # 2) ChromaDB
    vectors_stored = 0
    try:
        if vector_svc.available:
            vectors_stored = vector_svc.ingest(payload)
        else:
            logger.warning("Ingest: vector service not available, skipping ChromaDB")
    except Exception as e:
        logger.error("Ingest: vector_service.ingest failed: %s", e)

    logger.info(
        "Ingest complete: %s → %d entities, %d relations, %d vectors",
        video_url, entities_stored, relations_stored, vectors_stored,
    )

    return IngestResponse(
        status="ok",
        message=f"Ingested {video_url}",
        video_id=payload.video.video_id,
        entities_stored=entities_stored,
        relations_stored=relations_stored,
        vectors_stored=vectors_stored,
    )
