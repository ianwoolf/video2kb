"""
Transcoder Client — Pipeline 调用 Transcoder Service 的 HTTP 客户端

提交转写任务、轮询任务状态，含超时和重试。
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

TRANSCODER_URL = os.getenv("TRANSCODER_URL", "http://localhost:8002")
TRANSCODER_API_KEY = os.getenv("TRANSCODER_API_KEY", "")

# 轮询配置
DEFAULT_TIMEOUT = 600       # 最大等待秒数（10 分钟）
DEFAULT_INTERVAL = 5        # 轮询间隔秒数


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if TRANSCODER_API_KEY:
        h["X-API-Key"] = TRANSCODER_API_KEY
    return h


def submit_task(
    storage_id: str,
    storage_path: str = "",
    language: str = "zh",
    model: str = "base",
) -> Optional[dict]:
    """
    提交转写任务到 Transcoder。

    Returns:
        {"task_id": str, "status": "pending"}  或  None（失败）
    """
    url = f"{TRANSCODER_URL}/api/transcode"
    payload = {
        "storage_id": storage_id,
        "storage_path": storage_path,
        "language": language,
        "model": model,
    }
    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            logger.info("Transcoder: submitted task %s", result.get("task_id"))
            return result
        else:
            logger.error("Transcoder submit failed: HTTP %d — %s", resp.status_code, resp.text[:200])
            return None
    except requests.exceptions.ConnectionError:
        logger.error("Transcoder: connection failed (is Transcoder service running at %s?)", TRANSCODER_URL)
        return None
    except Exception as e:
        logger.error("Transcoder submit error: %s", e)
        return None


def poll_task(
    task_id: str,
    timeout: int = DEFAULT_TIMEOUT,
    interval: int = DEFAULT_INTERVAL,
) -> dict:
    """
    轮询转写任务状态，直到完成或超时。

    Returns:
        completed: {"status": "completed", "text": ..., "segments": [...], ...}
        failed:    {"status": "failed", "error": "..."}
        timeout:   {"status": "timeout", "last_status": "..."}
    """
    url = f"{TRANSCODER_URL}/api/transcode/{task_id}"
    start = time.time()
    last_status = "unknown"

    while time.time() - start < timeout:
        try:
            resp = requests.get(url, headers=_headers(), timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                last_status = data.get("status", "")

                if data["status"] == "completed":
                    logger.info("Transcoder: task %s completed", task_id)
                    return data
                elif data["status"] == "failed":
                    logger.error("Transcoder: task %s failed: %s", task_id, data.get("error"))
                    return data

                # pending / processing → 继续等待
                logger.debug("Transcoder: task %s is %s, waiting...", task_id, data["status"])
            else:
                logger.warning("Transcoder: status check failed HTTP %d", resp.status_code)
        except Exception as e:
            logger.warning("Transcoder: status check error: %s", e)

        time.sleep(interval)

    logger.warning("Transcoder: task %s timed out after %ds (last status: %s)", task_id, timeout, last_status)
    return {"status": "timeout", "last_status": last_status, "task_id": task_id}
