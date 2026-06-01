"""
shared — video2kb 共享包

包含 Schema 定义和抽象接口，Pipeline/Storage/Transcoder/KB 共用。
"""
from .schema import (
    Entity, EntityType, IngestPayload, IngestResponse,
    Platform, Relation, Summary, TranscriptSegment, VideoInfo,
)
from .interfaces import StorageBackend, TaskQueue

__all__ = [
    "Entity", "EntityType", "IngestPayload", "IngestResponse",
    "Platform", "Relation", "Summary", "TranscriptSegment", "VideoInfo",
    "StorageBackend", "TaskQueue",
]
