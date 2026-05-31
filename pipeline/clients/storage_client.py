"""
Storage Client — Pipeline 调用 Storage Service 的 HTTP 客户端

用于上传音频文件到 Storage，以及查询文件信息。
"""
from __future__ import annotations

import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

STORAGE_URL = os.getenv("STORAGE_URL", "http://localhost:8001")
STORAGE_API_KEY = os.getenv("STORAGE_API_KEY", "")


def _headers() -> dict:
    h = {}
    if STORAGE_API_KEY:
        h["X-API-Key"] = STORAGE_API_KEY
    return h


def upload_file(
    file_path: str,
    filename: str = "",
    content_type: str = "",
    metadata: Optional[dict] = None,
) -> Optional[dict]:
    """
    上传本地文件到 Storage。

    Returns:
        {"storage_id": str, "storage_path": str, "filename": str,
         "size_bytes": int, "content_type": str, "created_at": str}
        失败返回 None
    """
    p = Path(file_path)
    if not p.exists():
        logger.error("upload_file: file not found: %s", file_path)
        return None

    url = f"{STORAGE_URL}/api/upload"
    fname = filename or p.name
    try:
        files = {"file": (fname, p.open("rb"), content_type or "application/octet-stream")}
        form_data = {}
        if metadata:
            for k, v in metadata.items():
                form_data[k] = str(v)
        resp = requests.post(url, files=files, data=form_data, headers=_headers(), timeout=120)
        if resp.status_code == 200:
            result = resp.json()
            logger.info("Storage: uploaded %s → %s (%d bytes)",
                        fname, result.get("storage_id"), result.get("size_bytes"))
            return result
        else:
            logger.error("Storage upload failed: HTTP %d — %s", resp.status_code, resp.text[:200])
            return None
    except requests.exceptions.ConnectionError:
        logger.error("Storage: connection failed (is Storage service running at %s?)", STORAGE_URL)
        return None
    except Exception as e:
        logger.error("Storage upload error: %s", e)
        return None


def get_file_info(storage_id: str) -> Optional[dict]:
    """查询文件元信息"""
    url = f"{STORAGE_URL}/api/files/{storage_id}/info"
    try:
        resp = requests.get(url, headers=_headers(), timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        logger.error("Storage get_info error: %s", e)
        return None


def delete_file(storage_id: str) -> bool:
    """删除文件"""
    url = f"{STORAGE_URL}/api/files/{storage_id}"
    try:
        resp = requests.delete(url, headers=_headers(), timeout=30)
        return resp.status_code == 200
    except Exception as e:
        logger.error("Storage delete error: %s", e)
        return False
