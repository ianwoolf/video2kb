"""
KB Service 测试 — Ingest 接口（含存储路径字段）
"""
from __future__ import annotations

import pytest


class TestKBIngest:
    """KB Ingest 接口测试"""

    @pytest.fixture
    def kb_client(self):
        """创建 KB 服务的 TestClient（关闭真实数据库）"""
        import os
        import sys
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        os.environ["ENABLE_GRAPH"] = "false"
        os.environ["ENABLE_VECTOR"] = "false"
        os.environ["ENABLE_LLAMAINDEX"] = "false"
        os.environ["API_KEY"] = "test-key"
        os.environ["ZAI_API_KEY"] = ""

        from fastapi.testclient import TestClient
        from kb.app.main import app

        with TestClient(app) as client:
            yield client

        for key in ["ENABLE_GRAPH", "ENABLE_VECTOR", "ENABLE_LLAMAINDEX", "API_KEY", "ZAI_API_KEY"]:
            os.environ.pop(key, None)

    def _sample_payload(self, with_storage_paths=True):
        payload = {
            "video": {
                "platform": "youtube",
                "url": "https://youtube.com/watch?v=test123",
                "title": "Test Video",
                "description": "A test video for unit testing",
                "duration": 300,
                "video_id": "test123",
                "channel": "TestChannel",
                "published_at": "2026-01-01",
            },
            "transcript": "这是测试转写文本，用于验证 IngestPayload。",
            "transcript_segments": [
                {"start": 0.0, "end": 5.0, "text": "第一段测试内容"},
                {"start": 5.0, "end": 10.0, "text": "第二段测试内容"},
            ],
            "summary": {
                "full_summary": "这是一个测试视频的摘要内容",
                "key_points": ["要点一", "要点二", "要点三"],
                "word_count": 50,
            },
            "entities": [
                {"name": "测试实体A", "type": "Concept", "description": "测试描述", "confidence": 0.9},
                {"name": "测试实体B", "type": "Person", "description": "另一个人", "confidence": 0.8},
            ],
            "relations": [
                {"source": "测试实体A", "target": "测试实体B", "relation": "相关", "description": "A和B相关", "confidence": 0.7},
            ],
        }
        if with_storage_paths:
            payload.update({
                "audio_storage_id": "audio_001",
                "audio_storage_path": "/audio/test123.mp3",
                "transcript_storage_id": "transcript_001",
                "transcript_storage_path": "/transcripts/test123.txt",
            })
        else:
            payload.update({
                "audio_storage_id": "",
                "audio_storage_path": "",
                "transcript_storage_id": "",
                "transcript_storage_path": "",
            })
        return payload

    def test_ingest_with_storage_paths(self, kb_client):
        """Ingest 数据包包含存储路径字段（无字幕场景）"""
        response = kb_client.post("/api/ingest", json=self._sample_payload(with_storage_paths=True))

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["video_id"] == "test123"
        # graph/vector 关闭，存储计数应为 0
        assert data["entities_stored"] == 0
        assert data["vectors_stored"] == 0

    def test_ingest_without_storage_paths(self, kb_client):
        """Ingest 数据包不含存储路径（有字幕场景）"""
        response = kb_client.post("/api/ingest", json=self._sample_payload(with_storage_paths=False))

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_ingest_minimal_payload(self, kb_client):
        """最小化 payload（仅必填字段）"""
        payload = {
            "video": {
                "platform": "youtube",
                "url": "https://youtube.com/watch?v=minimal",
                "title": "Minimal",
            },
            "transcript": "",
            "summary": {"full_summary": "", "key_points": [], "word_count": 0},
            "entities": [],
            "relations": [],
        }
        response = kb_client.post("/api/ingest", json=payload)
        assert response.status_code == 200

    def test_root_status(self, kb_client):
        """根路由返回 KB 服务状态"""
        response = kb_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Video2KB — Knowledge Base"
        assert "endpoints" in data

    def test_query_entity_no_graph(self, kb_client):
        """图数据库关闭时查询实体返回错误"""
        response = kb_client.get("/api/query/entity?name=test")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "not available" in data["message"]

    def test_query_search_no_vector(self, kb_client):
        """向量数据库关闭时语义搜索返回错误"""
        response = kb_client.post("/api/query/search", json={"query_text": "测试", "top_k": 5})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
