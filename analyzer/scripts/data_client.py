#!/usr/bin/env python3
"""
Data Client — 与 Part 2 数据服务通信

功能：
- 将 IngestPayload 序列化为 JSON 并 POST 到 Part 2 的 /api/ingest 接口
- Part 2 不可用时缓存到本地 data/pending/ 目录
- 支持重试和补传
"""
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

# 配置
DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://localhost:8000")
DATA_SERVICE_API_KEY = os.getenv("DATA_SERVICE_API_KEY", "")
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒

# 默认 pending 目录（可被 run_pipeline 覆盖）
DEFAULT_PENDING_DIR = Path(__file__).parent.parent / "data" / "pending"


def _get_pending_dir(pending_dir: Optional[Path] = None) -> Path:
    """获取 pending 目录路径"""
    p = pending_dir or DEFAULT_PENDING_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def _save_pending(payload_dict: dict, pending_dir: Path) -> str:
    """将 payload 保存到 pending 目录，返回文件名"""
    pending_dir.mkdir(parents=True, exist_ok=True)
    # 用 video_id + 时间戳作为文件名
    video_id = payload_dict.get("video", {}).get("video_id", "unknown")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{video_id}_{ts}.json"
    filepath = pending_dir / filename
    filepath.write_text(json.dumps(payload_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("已缓存到 pending: %s", filepath)
    return str(filepath)


def send_to_part2(payload_dict: dict, pending_dir: Optional[Path] = None) -> dict:
    """
    将 IngestPayload 发送到 Part 2 /api/ingest 接口

    如果 Part 2 不可用，自动缓存到 pending 目录。
    返回 {"status": "ok"|"cached"|"error", ...}
    """
    url = f"{DATA_SERVICE_URL}/api/ingest"
    headers = {"Content-Type": "application/json"}
    if DATA_SERVICE_API_KEY:
        headers["X-API-Key"] = DATA_SERVICE_API_KEY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("发送数据到 Part 2 (尝试 %d/%d): %s", attempt, MAX_RETRIES, url)
            resp = requests.post(url, json=payload_dict, headers=headers, timeout=30)

            if resp.status_code == 200:
                result = resp.json()
                logger.info("发送成功: %s", result.get("message", ""))
                return {"status": "ok", "response": result}

            elif resp.status_code == 401:
                logger.error("Part 2 API Key 无效 (HTTP 401)")
                break

            elif resp.status_code == 422:
                logger.error("Part 2 数据格式错误 (HTTP 422): %s", resp.text[:500])
                break

            else:
                logger.warning("Part 2 返回 HTTP %d, 将重试...", resp.status_code)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
                continue

        except requests.exceptions.ConnectionError:
            logger.warning("Part 2 不可用 (连接失败), 尝试 %d/%d", attempt, MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
            continue

        except requests.exceptions.Timeout:
            logger.warning("Part 2 请求超时, 尝试 %d/%d", attempt, MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
            continue

        except Exception as e:
            logger.error("发送数据到 Part 2 失败: %s", e)
            break

    # 所有重试失败，缓存到本地
    logger.warning("Part 2 不可用，将数据缓存到本地 pending 目录")
    pending = _get_pending_dir(pending_dir)
    cached_path = _save_pending(payload_dict, pending)
    return {"status": "cached", "cached_path": cached_path}


def retry_pending(pending_dir: Optional[Path] = None) -> dict:
    """
    扫描 data/pending/ 目录，重新发送所有待补传文件。

    返回 {"total": int, "sent": int, "failed": int, "remaining": int}
    """
    pending = _get_pending_dir(pending_dir)
    json_files = sorted(pending.glob("*.json"))

    if not json_files:
        logger.info("没有待补传的文件")
        return {"total": 0, "sent": 0, "failed": 0, "remaining": 0}

    logger.info("找到 %d 个待补传文件", len(json_files))
    sent = 0
    failed = 0

    for filepath in json_files:
        try:
            payload = json.loads(filepath.read_text(encoding="utf-8"))
            result = send_to_part2_with_file(payload, pending)

            if result.get("status") == "ok":
                filepath.unlink(missing_ok=True)
                sent += 1
                logger.info("补传成功，已删除: %s", filepath.name)
            else:
                failed += 1
                logger.warning("补传失败: %s", filepath.name)
        except Exception as e:
            failed += 1
            logger.error("补传文件异常 (%s): %s", filepath.name, e)

    remaining = len(list(pending.glob("*.json")))
    logger.info("补传完成: 发送 %d, 失败 %d, 剩余 %d", sent, failed, remaining)
    return {"total": len(json_files), "sent": sent, "failed": failed, "remaining": remaining}


def send_to_part2_with_file(payload_dict: dict, pending_dir: Path) -> dict:
    """
    内部方法：发送数据到 Part 2，成功后删除对应的 pending 文件。
    与 send_to_part2 不同的是，这个方法不会在失败时再次缓存。
    """
    url = f"{DATA_SERVICE_URL}/api/ingest"
    headers = {"Content-Type": "application/json"}
    if DATA_SERVICE_API_KEY:
        headers["X-API-Key"] = DATA_SERVICE_API_KEY

    try:
        resp = requests.post(url, json=payload_dict, headers=headers, timeout=30)
        if resp.status_code == 200:
            return {"status": "ok", "response": resp.json()}
        else:
            logger.warning("Part 2 返回 HTTP %d: %s", resp.status_code, resp.text[:200])
            return {"status": "error", "status_code": resp.status_code}
    except Exception as e:
        logger.warning("连接 Part 2 失败: %s", e)
        return {"status": "error", "error": str(e)}
