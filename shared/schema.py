"""
video2kb 数据格式定义 — Part 1 和 Part 2 之间的通信协议

Part 1 分析完成后，将结果序列化为 JSON 并 POST 到 Part 2 的 /api/ingest 接口。
此文件为两边共享的 Schema 定义，确保数据格式一致。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────

class Platform(str, Enum):
    YOUTUBE = "youtube"
    BILIBILI = "bilibili"


class EntityType(str, Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    LOCATION = "Location"
    EVENT = "Event"
    CONCEPT = "Concept"
    WORK_OF_ART = "WorkOfArt"
    PRODUCT = "Product"
    OTHER = "Other"


# ── Sub-models ────────────────────────────────────────────────────────

class VideoInfo(BaseModel):
    """视频元信息"""
    platform: Platform
    url: str
    title: str = ""
    description: str = ""
    duration: int = 0                          # 秒
    video_id: str = ""                         # 平台视频 ID
    channel: str = ""                          # 频道/作者
    published_at: Optional[str] = None         # 发布时间


class Summary(BaseModel):
    """LLM 总结结果"""
    full_summary: str = ""
    key_points: List[str] = Field(default_factory=list)
    word_count: int = 0


class Entity(BaseModel):
    """实体"""
    name: str
    type: str = ""                             # EntityType 或自定义字符串
    description: str = ""                      # 实体描述（来自 LLM）
    confidence: float = 1.0


class Relation(BaseModel):
    """实体间关系"""
    source: str
    target: str
    relation: str = ""
    description: str = ""                      # 关系描述
    confidence: float = 1.0


class TranscriptSegment(BaseModel):
    """带时间戳的转写片段"""
    start: float = 0.0
    end: float = 0.0
    text: str = ""


# ── Top-level Payload ─────────────────────────────────────────────────

class IngestPayload(BaseModel):
    """Part 1 → Part 2 的完整数据包"""
    video: VideoInfo
    transcript: str = ""                       # 完整转写文本
    transcript_segments: List[TranscriptSegment] = Field(default_factory=list)
    summary: Summary
    entities: List[Entity] = Field(default_factory=list)
    relations: List[Relation] = Field(default_factory=list)
    analyzed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── 响应格式 ───────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    """Part 2 对 ingest 请求的响应"""
    status: str = "ok"                         # ok | error
    message: str = ""
    video_id: str = ""                         # 入库后的 video_id
    entities_stored: int = 0
    relations_stored: int = 0
    vectors_stored: int = 0
