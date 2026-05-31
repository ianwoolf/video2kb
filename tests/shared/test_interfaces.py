"""
接口契约测试 — 验证所有 StorageBackend / TaskQueue 实现满足抽象接口
"""
from __future__ import annotations

import pytest


class TestStorageBackendContract:
    """验证所有 StorageBackend 实现都满足接口契约"""

    def test_local_backend_implements_interface(self):
        """LocalStorageBackend 实现了 StorageBackend 所有方法"""
        from shared.interfaces import StorageBackend
        from storage.backends.local import LocalStorageBackend

        backend = LocalStorageBackend(base_dir="/tmp/video2kb-test-contract")
        assert isinstance(backend, StorageBackend)
        # 验证所有抽象方法都已实现
        assert callable(getattr(backend, "save", None))
        assert callable(getattr(backend, "get", None))
        assert callable(getattr(backend, "get_info", None))
        assert callable(getattr(backend, "delete", None))
        assert callable(getattr(backend, "exists", None))
        assert callable(getattr(backend, "list_files", None))

    def test_s3_backend_implements_interface(self):
        """S3StorageBackend 是 StorageBackend 的子类（空实现但不报错）"""
        from shared.interfaces import StorageBackend
        from storage.backends.local import S3StorageBackend

        backend = S3StorageBackend(endpoint="", bucket="")
        assert isinstance(backend, StorageBackend)

    def test_s3_backend_methods_raise_not_implemented(self):
        """S3StorageBackend 的所有方法都应抛出 NotImplementedError"""
        from storage.backends.local import S3StorageBackend
        from io import BytesIO

        backend = S3StorageBackend(endpoint="", bucket="")
        with pytest.raises(NotImplementedError):
            backend.save(BytesIO(b"data"), "test.txt")
        with pytest.raises(NotImplementedError):
            backend.get("nonexistent")
        with pytest.raises(NotImplementedError):
            backend.get_info("nonexistent")
        with pytest.raises(NotImplementedError):
            backend.delete("nonexistent")
        with pytest.raises(NotImplementedError):
            backend.exists("nonexistent")
        with pytest.raises(NotImplementedError):
            backend.list_files()


class TestTaskQueueContract:
    """验证所有 TaskQueue 实现都满足接口契约"""

    def test_memory_queue_implements_interface(self):
        """MemoryTaskQueue 实现了 TaskQueue 所有方法"""
        from shared.interfaces import TaskQueue
        from transcoder.app.queues.memory import MemoryTaskQueue

        queue = MemoryTaskQueue()
        assert isinstance(queue, TaskQueue)
        assert callable(getattr(queue, "submit", None))
        assert callable(getattr(queue, "get_task_status", None))
        assert callable(getattr(queue, "start_worker", None))
        assert callable(getattr(queue, "stop_worker", None))
        assert callable(getattr(queue, "update_task_status", None))
