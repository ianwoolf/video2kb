"""
Transcoder Service 测试 — API 接口 + 内存队列单元测试
"""
from __future__ import annotations

import pytest
import threading


class TestMemoryQueue:
    """内存任务队列单元测试"""

    def test_submit_and_get_status(self):
        """提交任务 → 立即可查"""
        from transcoder.app.queues.memory import MemoryTaskQueue
        queue = MemoryTaskQueue()

        queue.submit("task_1", {"audio_path": "/tmp/test.mp3"})

        status = queue.get_task_status("task_1")
        assert status is not None
        assert status["status"] == "pending"
        assert status["task_data"]["audio_path"] == "/tmp/test.mp3"

    def test_nonexistent_task(self):
        """查询不存在的任务返回 None"""
        from transcoder.app.queues.memory import MemoryTaskQueue
        queue = MemoryTaskQueue()
        assert queue.get_task_status("nonexistent") is None

    def test_update_status(self):
        """手动更新任务状态"""
        from transcoder.app.queues.memory import MemoryTaskQueue
        queue = MemoryTaskQueue()

        queue.submit("task_1", {"data": "test"})
        queue.update_task_status("task_1", "completed", result={"text": "done"})

        status = queue.get_task_status("task_1")
        assert status["status"] == "completed"
        assert status["result"]["text"] == "done"

    def test_update_status_failed(self):
        """更新任务为失败状态"""
        from transcoder.app.queues.memory import MemoryTaskQueue
        queue = MemoryTaskQueue()

        queue.submit("task_1", {"data": "test"})
        queue.update_task_status("task_1", "failed", error="模型加载失败")

        status = queue.get_task_status("task_1")
        assert status["status"] == "failed"
        assert status["error"] == "模型加载失败"

    def test_worker_processes_task(self):
        """worker 线程处理任务 → 状态变为 completed"""
        from transcoder.app.queues.memory import MemoryTaskQueue
        queue = MemoryTaskQueue()

        results = {}

        def handler(task_id, task_data):
            # 模拟处理
            import time
            time.sleep(0.1)
            queue.update_task_status(task_id, "completed", result={"processed": True})

        queue.submit("task_1", {"data": "test"})
        queue.start_worker(handler)

        # 等待处理完成
        import time
        for _ in range(20):
            status = queue.get_task_status("task_1")
            if status and status["status"] == "completed":
                break
            time.sleep(0.05)
        else:
            pytest.fail("Task not completed within timeout")

        queue.stop_worker()

    def test_worker_handles_failure(self):
        """worker 处理失败 → 状态变为 failed"""
        from transcoder.app.queues.memory import MemoryTaskQueue
        queue = MemoryTaskQueue()

        def failing_handler(task_id, task_data):
            raise RuntimeError("模拟处理失败")

        queue.submit("task_1", {"data": "test"})
        queue.start_worker(failing_handler)

        import time
        for _ in range(20):
            status = queue.get_task_status("task_1")
            if status and status["status"] == "failed":
                break
            time.sleep(0.05)
        else:
            pytest.fail("Task not marked as failed within timeout")

        queue.stop_worker()

    def test_multiple_tasks(self):
        """提交多个任务"""
        from transcoder.app.queues.memory import MemoryTaskQueue
        queue = MemoryTaskQueue()

        for i in range(5):
            queue.submit(f"task_{i}", {"index": i})

        for i in range(5):
            status = queue.get_task_status(f"task_{i}")
            assert status is not None
            assert status["status"] == "pending"

    def test_stop_worker(self):
        """停止 worker 后不再处理新任务"""
        from transcoder.app.queues.memory import MemoryTaskQueue
        queue = MemoryTaskQueue()

        def handler(task_id, task_data):
            import time
            time.sleep(0.5)
            queue.update_task_status(task_id, "completed")

        queue.start_worker(handler)
        queue.stop_worker()

        # 停止后提交的任务应保持 pending
        queue.submit("task_after_stop", {"data": "test"})
        status = queue.get_task_status("task_after_stop")
        assert status["status"] == "pending"


class TestTranscoderAPI:
    """Transcoder API 接口测试（使用 FastAPI TestClient）"""

    @pytest.fixture
    def transcoder_client(self):
        """创建 Transcoder 服务的 TestClient（不加载 Whisper 模型）"""
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

        # 启动 lifespan（会加载模型，可能失败）
        with TestClient(app) as client:
            yield client

        for key in ["TASK_QUEUE", "API_KEY", "STORAGE_URL", "WHISPER_MODEL"]:
            os.environ.pop(key, None)

    def test_submit_task(self, transcoder_client):
        """提交转写任务 → 返回 task_id"""
        payload = {
            "storage_id": "audio_001",
            "storage_path": "/audio/test.mp3",
            "language": "zh",
            "model": "base",
        }
        response = transcoder_client.post("/api/transcode", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"

    def test_query_task_status(self, transcoder_client):
        """查询任务状态"""
        payload = {"storage_id": "audio_001", "language": "zh"}
        resp = transcoder_client.post("/api/transcode", json=payload)
        task_id = resp.json()["task_id"]

        response = transcoder_client.get(f"/api/transcode/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] in ("pending", "processing", "completed", "failed")

    def test_query_nonexistent_task(self, transcoder_client):
        """查询不存在的任务返回 404"""
        response = transcoder_client.get("/api/transcode/nonexistent_task")
        assert response.status_code == 404

    def test_root_status(self, transcoder_client):
        """根路由返回服务状态"""
        response = transcoder_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Video2KB — Transcoder Service"
        assert "whisper" in data
        assert "endpoints" in data
