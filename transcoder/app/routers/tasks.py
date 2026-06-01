"""
Transcoder API — 提交转写任务、查询任务状态
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["transcode"])


class TranscodeRequest(BaseModel):
    storage_id: str
    storage_path: str = ""
    language: str = "zh"
    model: str = "base"


@router.post("/api/transcode")
async def submit_transcode(request: Request, body: TranscodeRequest):
    """提交音频转写任务"""
    task_queue = request.app.state.task_queue

    task_id = uuid.uuid4().hex[:12]
    task_queue.submit(task_id, {
        "storage_id": body.storage_id,
        "storage_path": body.storage_path,
        "language": body.language,
        "model": body.model,
    })

    return {"task_id": task_id, "status": "pending"}


@router.get("/api/transcode/{task_id}")
async def get_transcode_status(task_id: str, request: Request):
    """查询转写任务状态"""
    task_queue = request.app.state.task_queue

    status = task_queue.get_task_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # 返回结果时排除内部 task_data
    result = {
        "task_id": status["task_id"],
        "status": status["status"],
        "created_at": status["created_at"],
        "updated_at": status["updated_at"],
    }
    if status["status"] == "completed" and status.get("result"):
        result["text"] = status["result"].get("text", "")
        result["segments"] = status["result"].get("segments", [])
        result["duration"] = status["result"].get("duration", 0)
        result["audio_storage_id"] = status["result"].get("audio_storage_id", "")
        result["transcript_storage_id"] = status["result"].get("transcript_storage_id", "")
        result["transcript_text_storage_id"] = status["result"].get("transcript_text_storage_id", "")
        result["transcript_srt_storage_id"] = status["result"].get("transcript_srt_storage_id", "")
    if status["status"] == "failed":
        result["error"] = status.get("error", "Unknown error")

    return result
