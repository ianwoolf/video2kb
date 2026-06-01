"""
Storage Service API — 文件上传、下载、查询、删除
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["files"])


async def _get_backend(request: Request):
    """从 app state 获取 StorageBackend 实例"""
    return request.app.state.storage_backend


@router.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    video_id: Optional[str] = Form(None),
    file_type: Optional[str] = Form(None),
    request: Request = None,
):
    """上传文件到 Storage"""
    backend = await _get_backend(request)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    metadata = {}
    if video_id:
        metadata["video_id"] = video_id
    if file_type:
        metadata["type"] = file_type

    # 读取上传的文件内容
    file_data = await file.read()
    from io import BytesIO
    result = backend.save(
        BytesIO(file_data),
        filename=file.filename,
        content_type=file.content_type or "",
        metadata=metadata or None,
    )

    return result


@router.get("/api/files/{storage_id}")
async def download_file(storage_id: str, request: Request = None):
    """下载文件"""
    backend = await _get_backend(request)

    info = backend.get_info(storage_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"File not found: {storage_id}")

    data = backend.get(storage_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"File data not found: {storage_id}")

    return Response(
        content=data,
        media_type=info.get("content_type", "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{info["filename"]}"'},
    )


@router.get("/api/files/{storage_id}/info")
async def get_file_info(storage_id: str, request: Request = None):
    """获取文件元信息"""
    backend = await _get_backend(request)

    info = backend.get_info(storage_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"File not found: {storage_id}")

    return info


@router.delete("/api/files/{storage_id}")
async def delete_file(storage_id: str, request: Request = None):
    """删除文件"""
    backend = await _get_backend(request)

    if not backend.exists(storage_id):
        raise HTTPException(status_code=404, detail=f"File not found: {storage_id}")

    success = backend.delete(storage_id)
    if not success:
        raise HTTPException(status_code=500, detail="Delete failed")

    return {"status": "ok", "storage_id": storage_id}


@router.get("/api/files")
async def list_files(prefix: str = "", limit: int = 100, request: Request = None):
    """列出文件"""
    backend = await _get_backend(request)
    results = backend.list_files(prefix=prefix, limit=limit)
    return {"status": "ok", "count": len(results), "files": results}
