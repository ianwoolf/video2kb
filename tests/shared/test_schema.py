"""
Schema 单元测试 — 序列化/反序列化、字段校验

验证 IngestPayload 新增的存储路径字段正确工作。
"""
from __future__ import annotations

import pytest
from shared.schema import (
    IngestPayload, VideoInfo, Summary, Entity, Relation,
    TranscriptSegment, Platform, EntityType,
    IngestResponse,
)


class TestIngestPayload:
    """IngestPayload 序列化/反序列化测试"""

    def test_roundtrip_with_storage_fields(self):
        """含存储路径的 payload 序列化 → 反序列化 → 一致"""
        payload = IngestPayload(
            video=VideoInfo(
                platform=Platform.YOUTUBE,
                url="https://youtube.com/watch?v=test123",
                title="Test Video",
                video_id="test123",
            ),
            transcript="测试转写文本",
            transcript_segments=[
                TranscriptSegment(start=0.0, end=5.0, text="第一段"),
                TranscriptSegment(start=5.0, end=10.0, text="第二段"),
            ],
            summary=Summary(
                full_summary="测试摘要",
                key_points=["要点一", "要点二"],
                word_count=50,
            ),
            entities=[
                Entity(name="测试实体", type="Concept", description="描述", confidence=0.9),
            ],
            relations=[
                Relation(source="A", target="B", relation="相关", description="A和B相关"),
            ],
            # 第三波新增字段
            audio_storage_id="audio_abc123",
            audio_storage_path="/audio/abc123.mp3",
            transcript_storage_id="transcript_xyz",
            transcript_storage_path="/transcripts/abc123.txt",
        )

        # 序列化
        json_str = payload.model_dump_json()

        # 反序列化
        payload2 = IngestPayload.model_validate_json(json_str)

        assert payload2.video.video_id == "test123"
        assert payload2.video.platform == Platform.YOUTUBE
        assert payload2.audio_storage_id == "audio_abc123"
        assert payload2.audio_storage_path == "/audio/abc123.mp3"
        assert payload2.transcript_storage_id == "transcript_xyz"
        assert payload2.transcript_storage_path == "/transcripts/abc123.txt"
        assert len(payload2.transcript_segments) == 2
        assert len(payload2.entities) == 1

    def test_storage_fields_default_empty(self):
        """存储路径字段默认为空字符串（有字幕场景）"""
        payload = IngestPayload(
            video=VideoInfo(platform=Platform.YOUTUBE, url="http://test"),
            summary=Summary(),
        )
        assert payload.audio_storage_id == ""
        assert payload.audio_storage_path == ""
        assert payload.transcript_storage_id == ""
        assert payload.transcript_storage_path == ""
        assert payload.transcript == ""
        assert payload.entities == []
        assert payload.relations == []

    def test_bilibili_platform(self):
        """Bilibili 平台 payload"""
        payload = IngestPayload(
            video=VideoInfo(platform=Platform.BILIBILI, url="https://bilibili.com/video/BV1test"),
            summary=Summary(),
        )
        assert payload.video.platform == Platform.BILIBILI
        json_str = payload.model_dump_json()
        assert '"platform":"bilibili"' in json_str or '"platform": "bilibili"' in json_str

    def test_ingest_response(self):
        """IngestResponse 序列化"""
        resp = IngestResponse(
            status="ok",
            message="Ingested",
            video_id="test123",
            entities_stored=5,
            relations_stored=3,
            vectors_stored=8,
        )
        json_str = resp.model_dump_json()
        data = IngestResponse.model_validate_json(json_str)
        assert data.entities_stored == 5
