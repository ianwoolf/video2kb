"""
Storage Client — Transcoder 调用 Storage Service 的 HTTP 客户端
"""
from __future__ import annotations

import logging
import os
from io import BytesIO
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


def download_file(storage_id: str) -> Optional[bytes]:
    """从 Storage 下载文件内容"""
    url = f"{STORAGE_URL}/api/files/{storage_id}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=120)
        if resp.status_code == 200:
            return resp.content
        else:
            logger.error("Storage download failed: HTTP %d — %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.error("Storage download error: %s", e)
        return None


def download_to_file(storage_id: str, save_path: str) -> bool:
    """从 Storage 下载文件并保存到本地路径"""
    data = download_file(storage_id)
    if data is None:
        return False
    from pathlib import Path
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    Path(save_path).write_bytes(data)
    logger.info("Storage: downloaded %s → %s (%d bytes)", storage_id, save_path, len(data))
    return True


def upload_file_bytes(data: bytes, filename: str, content_type: str = "", metadata: Optional[dict] = None) -> Optional[dict]:
    """上传字节数据到 Storage"""
    url = f"{STORAGE_URL}/api/upload"
    try:
        files = {"file": (filename, BytesIO(data), content_type)}
        form_data = {}
        if metadata:
            for k, v in metadata.items():
                form_data[k] = str(v)
        resp = requests.post(url, files=files, data=form_data, headers=_headers(), timeout=120)
        if resp.status_code == 200:
            result = resp.json()
            logger.info("Storage: uploaded %s → %s", filename, result.get("storage_id"))
            return result
        else:
            logger.error("Storage upload failed: HTTP %d — %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.error("Storage upload error: %s", e)
        return None


def upload_file_path(file_path: str, filename: str = "", content_type: str = "", metadata: Optional[dict] = None) -> Optional[dict]:
    """上传本地文件到 Storage"""
    from pathlib import Path
    p = Path(file_path)
    if not p.exists():
        logger.error("File not found: %s", file_path)
        return None
    fname = filename or p.name
    return upload_file_bytes(p.read_bytes(), fname, content_type, metadata)


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
