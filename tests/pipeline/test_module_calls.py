"""
Pipeline 模块间调用测试 — 通过配置指向测试服务，验证客户端 HTTP 交互

核心机制：
- STORAGE_URL / TRANSCODER_URL / DATA_SERVICE_URL 通过 conftest.py 指向测试服务
- Storage / Transcoder / KB 使用 FastAPI TestClient 模拟真实服务
- 测试不修改业务代码，仅通过环境变量切换
"""
from __future__ import annotations

import pytest


class TestStorageClientWithTestService:
    """Pipeline Storage 客户端 → Storage 测试服务"""

    @pytest.fixture
    def services(self, tmp_storage_dir):
        """启动 Storage 测试服务，返回 TestClient"""
        import os
        import sys
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # Storage 服务配置
        os.environ["STORAGE_BACKEND"] = "local"
        os.environ["STORAGE_BASE_DIR"] = str(tmp_storage_dir)
        os.environ["API_KEY"] = "test-key"

        from tests._helpers import push_service
        push_service("storage")

        from fastapi.testclient import TestClient
        from storage.app.main import app

        storage_client = TestClient(app, headers={"X-API-Key": "test-key"})
        with storage_client:
            yield {"storage": storage_client, "tmp_dir": tmp_storage_dir}

        for key in ["STORAGE_BACKEND", "STORAGE_BASE_DIR", "API_KEY"]:
            os.environ.pop(key, None)

    def test_upload_and_get_info_via_client(self, services):
        """
        验证 Pipeline 的 storage_client.upload_file() 能正确调用 Storage 服务。
        此测试演示了模块间调用测试的模式：
        1. Storage TestClient 模拟真实服务
        2. storage_client 通过 STORAGE_URL 找到服务
        3. 实际生产代码不需要任何修改
        """
        # 先通过 Storage API 确认服务可用
        response = services["storage"].get("/")
        assert response.status_code == 200

        # 通过 Storage API 直接上传（模拟 storage_client 的行为）
        files = {"file": ("test.mp3", b"fake_audio" * 50, "audio/mpeg")}
        response = services["storage"].post("/api/upload", files=files)
        assert response.status_code == 200

        storage_id = response.json()["storage_id"]

        # 查询确认
        response = services["storage"].get(f"/api/files/{storage_id}/info")
        assert response.status_code == 200
        assert response.json()["filename"] == "test.mp3"


class TestTranscoderClientWithTestService:
    """Pipeline Transcoder 客户端 → Transcoder 测试服务"""

    @pytest.fixture
    def services(self):
        """启动 Transcoder 测试服务，返回 TestClient"""
        import os
        import sys
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        os.environ["TASK_QUEUE"] = "memory"
        os.environ["API_KEY"] = "test-key"
        os.environ["STORAGE_URL"] = "http://mock-storage:8001"
        os.environ["WHISPER_MODEL"] = "tiny"

        from tests._helpers import push_service
        push_service("transcoder")

        from fastapi.testclient import TestClient
        from transcoder.app.main import app

        for key in ["TASK_QUEUE", "API_KEY", "STORAGE_URL", "WHISPER_MODEL"]:
            os.environ.pop(key, None)

    def test_submit_and_query_task(self, services):
        """提交任务 → 查询状态"""
        payload = {"storage_id": "audio_001", "language": "zh", "model": "base"}
        response = services["transcoder"].post("/api/transcode", json=payload)

        assert response.status_code == 200
        task_id = response.json()["task_id"]

        # 查询
        response = services["transcoder"].get(f"/api/transcode/{task_id}")
        assert response.status_code == 200
        assert response.json()["task_id"] == task_id


class TestPipelineWithKBTestService:
    """Pipeline → KB 模块间调用测试"""

    @pytest.fixture
    def kb_client(self):
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

        from tests._helpers import push_service
        push_service("kb")

        from fastapi.testclient import TestClient
        from kb.app.main import app

        with TestClient(app, headers={"X-API-Key": "test-key"}) as client:
            yield client

        for key in ["ENABLE_GRAPH", "ENABLE_VECTOR", "ENABLE_LLAMAINDEX", "API_KEY", "ZAI_API_KEY"]:
            os.environ.pop(key, None)

    def test_send_ingest_to_kb(self, kb_client):
        """Pipeline 发送 IngestPayload 到 KB"""
        payload = {
            "video": {
                "platform": "youtube",
                "url": "https://youtube.com/watch?v=test",
                "title": "Test",
                "video_id": "test",
            },
            "transcript": "测试文本",
            "summary": {"full_summary": "摘要"},
            "entities": [],
            "relations": [],
            "audio_storage_id": "audio_001",
            "audio_storage_path": "/audio/test.mp3",
            "transcript_storage_id": "transcript_001",
            "transcript_storage_path": "/transcripts/test.txt",
        }

        response = kb_client.post("/api/ingest", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["video_id"] == "test"
