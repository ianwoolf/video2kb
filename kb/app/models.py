"""
请求 / 响应模型 — 从 shared 导入核心 Schema，补充 KB 专用模型
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

# 让 import 能找到 shared 包
_SHARED_DIR = str(Path(__file__).resolve().parents[2] / "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

from schema import IngestPayload, IngestResponse  # noqa: E402

__all__ = ["IngestPayload", "IngestResponse"]


# ── 通用 API 响应包装 ──────────────────────────────────────────────────

class ApiResponse(BaseModel):
    """统一响应格式"""
    status: str = "ok"  # ok | error
    data: Optional[object] = None
    message: str = ""


# ── 查询请求体 ────────────────────────────────────────────────────────

class SearchQuery(BaseModel):
    query_text: str
    top_k: int = Field(default=10, ge=1, le=100)
