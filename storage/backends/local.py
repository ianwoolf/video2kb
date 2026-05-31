"""
Storage Backends — 文件存储后端实现
"""
from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional

from shared.interfaces import StorageBackend

logger = logging.getLogger(__name__)


class LocalStorageBackend(StorageBackend):
    """本地文件系统存储后端（默认实现）"""

    def __init__(self, base_dir: str = "data/storage"):
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        # 元数据存储目录
        self._meta_dir = self._base_dir / ".meta"
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorageBackend: base_dir=%s", self._base_dir.resolve())

    def _meta_path(self, storage_id: str) -> Path:
        return self._meta_dir / f"{storage_id}.json"

    def _file_path(self, storage_id: str, filename: str) -> Path:
        """根据 storage_id 和 filename 计算文件存储路径（按日期分目录）"""
        # 按年月分目录避免单目录文件过多
        date_prefix = datetime.now().strftime("%Y%m")
        category = self._guess_category(filename)
        return self._base_dir / category / date_prefix / f"{storage_id}_{filename}"

    @staticmethod
    def _guess_category(filename: str) -> str:
        """根据文件扩展名猜测分类目录"""
        ext = Path(filename).suffix.lower()
        audio_exts = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".webm", ".aac"}
        text_exts = {".txt", ".srt", ".vtt", ".json", ".md", ".csv"}
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
        if ext in audio_exts:
            return "audio"
        elif ext in text_exts:
            return "transcripts"
        elif ext in video_exts:
            return "video"
        return "other"

    def save(self, file_data: BinaryIO, filename: str, content_type: str = "", metadata: Optional[Dict] = None) -> dict:
        storage_id = uuid.uuid4().hex[:12]
        file_path = self._file_path(storage_id, filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file_data, f)

        size_bytes = file_path.stat().st_size
        now = datetime.now().isoformat()

        meta = {
            "storage_id": storage_id,
            "filename": filename,
            "storage_path": str(file_path),
            "size_bytes": size_bytes,
            "content_type": content_type,
            "created_at": now,
            "metadata": metadata or {},
        }
        self._meta_path(storage_id).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        logger.info("LocalStorageBackend: saved %s → %s (%d bytes)", filename, storage_id, size_bytes)
        return meta

    def get(self, storage_id: str) -> Optional[bytes]:
        meta = self.get_info(storage_id)
        if not meta:
            return None
        file_path = Path(meta.get("storage_path", ""))
        if not file_path.exists():
            return None
        return file_path.read_bytes()

    def get_info(self, storage_id: str) -> Optional[dict]:
        mp = self._meta_path(storage_id)
        if not mp.exists():
            return None
        return json.loads(mp.read_text(encoding="utf-8"))

    def delete(self, storage_id: str) -> bool:
        meta = self.get_info(storage_id)
        if not meta:
            return False
        # 删除文件
        file_path = Path(meta.get("storage_path", ""))
        if file_path.exists():
            file_path.unlink()
        # 删除元数据
        self._meta_path(storage_id).unlink(missing_ok=True)
        logger.info("LocalStorageBackend: deleted %s", storage_id)
        return True

    def exists(self, storage_id: str) -> bool:
        return self._meta_path(storage_id).exists()

    def list_files(self, prefix: str = "", limit: int = 100) -> List[dict]:
        results = []
        for mp in self._meta_dir.glob("*.json"):
            if len(results) >= limit:
                break
            try:
                meta = json.loads(mp.read_text(encoding="utf-8"))
                if prefix:
                    # 按分类目录前缀过滤
                    category = self._guess_category(meta.get("filename", ""))
                    if not category.startswith(prefix):
                        continue
                results.append(meta)
            except Exception:
                continue
        return results


class S3StorageBackend(StorageBackend):
    """
    S3 / MinIO 存储后端（空实现）。

    TODO: 使用 boto3 实现 save/get/delete 等方法。
    当前仅作为接口占位，确保 StorageBackend 接口可扩展。
    """

    def __init__(self, endpoint: str = "", bucket: str = "", access_key: str = "",
                 secret_key: str = "", region: str = "us-east-1"):
        self._endpoint = endpoint
        self._bucket = bucket
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region
        logger.warning("S3StorageBackend: initialized but not fully implemented (stub)")

    def save(self, file_data: BinaryIO, filename: str, content_type: str = "", metadata: Optional[Dict] = None) -> dict:
        raise NotImplementedError("S3StorageBackend.save() not yet implemented. Use STORAGE_BACKEND=local for now.")

    def get(self, storage_id: str) -> Optional[bytes]:
        raise NotImplementedError("S3StorageBackend.get() not yet implemented.")

    def get_info(self, storage_id: str) -> Optional[dict]:
        raise NotImplementedError("S3StorageBackend.get_info() not yet implemented.")

    def delete(self, storage_id: str) -> bool:
        raise NotImplementedError("S3StorageBackend.delete() not yet implemented.")

    def exists(self, storage_id: str) -> bool:
        raise NotImplementedError("S3StorageBackend.exists() not yet implemented.")

    def list_files(self, prefix: str = "", limit: int = 100) -> List[dict]:
        raise NotImplementedError("S3StorageBackend.list_files() not yet implemented.")
