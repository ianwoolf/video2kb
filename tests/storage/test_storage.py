"""
Storage Service 测试 — API 接口 + LocalStorageBackend 单元测试
"""
from __future__ import annotations

import pytest
from io import BytesIO
from pathlib import Path


class TestLocalBackend:
    """本地文件系统后端单元测试"""

    def test_save_and_get(self, tmp_storage_dir):
        """保存文件 → 读取 → 内容一致"""
        from storage.backends.local import LocalStorageBackend
        backend = LocalStorageBackend(base_dir=str(tmp_storage_dir))

        content = b"hello world test content"
        result = backend.save(BytesIO(content), "test.txt", "text/plain")

        assert "storage_id" in result
        assert result["filename"] == "test.txt"
        assert result["size_bytes"] == len(content)
        assert result["content_type"] == "text/plain"

        retrieved = backend.get(result["storage_id"])
        assert retrieved == content

    def test_save_with_metadata(self, tmp_storage_dir):
        """保存文件时携带 metadata"""
        from storage.backends.local import LocalStorageBackend
        backend = LocalStorageBackend(base_dir=str(tmp_storage_dir))

        result = backend.save(
            BytesIO(b"audio data"),
            "test.mp3",
            "audio/mpeg",
            metadata={"video_id": "abc123", "type": "audio"},
        )

        info = backend.get_info(result["storage_id"])
        assert info["metadata"]["video_id"] == "abc123"
        assert info["metadata"]["type"] == "audio"

    def test_save_categorizes_by_extension(self, tmp_storage_dir):
        """文件按扩展名自动分类到子目录"""
        from storage.backends.local import LocalStorageBackend
        backend = LocalStorageBackend(base_dir=str(tmp_storage_dir))

        # 音频文件 → audio/ 目录
        r1 = backend.save(BytesIO(b"mp3"), "song.mp3", "audio/mpeg")
        assert "/audio/" in r1["storage_path"]

        # 文本文件 → transcripts/ 目录
        r2 = backend.save(BytesIO(b"text"), "sub.srt", "text/plain")
        assert "/transcripts/" in r2["storage_path"]

        # 未知类型 → other/ 目录
        r3 = backend.save(BytesIO(b"bin"), "data.xyz", "application/octet-stream")
        assert "/other/" in r3["storage_path"]

    def test_exists(self, tmp_storage_dir):
        """exists 判断"""
        from storage.backends.local import LocalStorageBackend
        backend = LocalStorageBackend(base_dir=str(tmp_storage_dir))

        result = backend.save(BytesIO(b"data"), "f.txt", "text/plain")
        assert backend.exists(result["storage_id"])
        assert not backend.exists("nonexistent")

    def test_delete(self, tmp_storage_dir):
        """删除文件"""
        from storage.backends.local import LocalStorageBackend
        backend = LocalStorageBackend(base_dir=str(tmp_storage_dir))

        result = backend.save(BytesIO(b"data"), "f.txt", "text/plain")
        assert backend.delete(result["storage_id"])
        assert not backend.exists(result["storage_id"])

    def test_delete_nonexistent(self, tmp_storage_dir):
        """删除不存在的文件返回 False"""
        from storage.backends.local import LocalStorageBackend
        backend = LocalStorageBackend(base_dir=str(tmp_storage_dir))
        assert not backend.delete("nonexistent")

    def test_get_info_nonexistent(self, tmp_storage_dir):
        """查询不存在的文件返回 None"""
        from storage.backends.local import LocalStorageBackend
        backend = LocalStorageBackend(base_dir=str(tmp_storage_dir))
        assert backend.get_info("nonexistent") is None

    def test_get_nonexistent(self, tmp_storage_dir):
        """读取不存在的文件返回 None"""
        from storage.backends.local import LocalStorageBackend
        backend = LocalStorageBackend(base_dir=str(tmp_storage_dir))
        assert backend.get("nonexistent") is None

    def test_list_files(self, tmp_storage_dir):
        """列出文件"""
        from storage.backends.local import LocalStorageBackend
        backend = LocalStorageBackend(base_dir=str(tmp_storage_dir))

        backend.save(BytesIO(b"a1"), "a.mp3", "audio/mpeg")
        backend.save(BytesIO(b"a2"), "a2.mp3", "audio/mpeg")
        backend.save(BytesIO(b"t1"), "t.txt", "text/plain")

        all_files = backend.list_files()
        assert len(all_files) == 3

        audio_files = backend.list_files(prefix="audio")
        assert len(audio_files) == 2


class TestStorageAPI:
    """Storage API 接口测试（使用 FastAPI TestClient）"""

    @pytest.fixture
    def storage_client(self, tmp_storage_dir):
        """创建 Storage 服务的 TestClient"""
        import os
        os.environ["STORAGE_BACKEND"] = "local"
        os.environ["STORAGE_BASE_DIR"] = str(tmp_storage_dir)
        os.environ["STORAGE_API_KEY"] = "test-key"

        # 需要让 import 能找到 storage 模块
        import sys
        project_root = Path(__file__).resolve().parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from fastapi.testclient import TestClient
        from storage.app.main import app

        client = TestClient(app)
        yield client

        # 清理环境变量
        for key in ["STORAGE_BACKEND", "STORAGE_BASE_DIR", "STORAGE_API_KEY"]:
            os.environ.pop(key, None)

    def test_upload_file(self, storage_client, sample_audio_bytes):
        """上传文件 → 返回 storage_id"""
        files = {"file": ("test_audio.mp3", sample_audio_bytes, "audio/mpeg")}

        response = storage_client.post("/api/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "storage_id" in data
        assert data["filename"] == "test_audio.mp3"
        assert data["size_bytes"] == len(sample_audio_bytes)
        assert data["content_type"] == "audio/mpeg"
        assert "storage_path" in data
        return data["storage_id"]

    def test_upload_with_form_metadata(self, storage_client):
        """上传时带 metadata"""
        files = {"file": ("report.txt", b"test content", "text/plain")}
        data = {"video_id": "abc123", "file_type": "transcript"}

        response = storage_client.post("/api/upload", files=files, data=data)
        assert response.status_code == 200

    def test_get_file_info(self, storage_client):
        """查询文件元信息"""
        storage_id = self.test_upload_file(storage_client)

        response = storage_client.get(f"/api/files/{storage_id}/info")
        assert response.status_code == 200
        data = response.json()
        assert data["storage_id"] == storage_id

    def test_get_file_download(self, storage_client, sample_audio_bytes):
        """下载文件"""
        storage_id = self.test_upload_file(storage_client)

        response = storage_client.get(f"/api/files/{storage_id}")
        assert response.status_code == 200
        assert response.content == sample_audio_bytes

    def test_get_nonexistent_file(self, storage_client):
        """查询不存在的文件返回 404"""
        response = storage_client.get("/api/files/nonexistent_id/info")
        assert response.status_code == 404

    def test_delete_file(self, storage_client):
        """删除文件"""
        storage_id = self.test_upload_file(storage_client)

        response = storage_client.delete(f"/api/files/{storage_id}")
        assert response.status_code == 200

        # 删除后再查应返回 404
        response = storage_client.get(f"/api/files/{storage_id}/info")
        assert response.status_code == 404

    def test_root_status(self, storage_client):
        """根路由返回服务状态"""
        response = storage_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Video2KB — Storage Service"
        assert "endpoints" in data

    def test_api_key_auth(self, storage_client):
        """API Key 认证测试"""
        import os
        # 用错误的 API Key
        original = os.environ.get("STORAGE_API_KEY")
        os.environ["STORAGE_API_KEY"] = "wrong-key"

        # 需要重新创建 app（middleware 在启动时绑定）
        from storage.app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)

        response = client.get("/api/files/any")
        assert response.status_code == 401

        if original is not None:
            os.environ["STORAGE_API_KEY"] = original
        else:
            os.environ.pop("STORAGE_API_KEY", None)
