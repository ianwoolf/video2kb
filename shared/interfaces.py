"""
video2kb 抽象接口定义 — StorageBackend + TaskQueue

所有存储后端和任务队列必须实现这些接口，确保可替换性。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO, Callable, Dict, List, Optional


# ── StorageBackend ───────────────────────────────────────────────────

class StorageBackend(ABC):
    """
    物料存储后端抽象基类。

    实现：LocalStorageBackend（本地文件系统，默认）
    预留：S3StorageBackend（MinIO/S3，空实现）
    """

    @abstractmethod
    def save(self, file_data: BinaryIO, filename: str, content_type: str = "", metadata: Optional[Dict] = None) -> dict:
        """
        保存文件。

        Args:
            file_data: 文件二进制流
            filename: 原始文件名
            content_type: MIME 类型
            metadata: 可选的元数据字典（如 video_id, type 等）

        Returns:
            {"storage_id": str, "storage_path": str, "filename": str,
             "size_bytes": int, "content_type": str, "created_at": str}
        """

    @abstractmethod
    def get(self, storage_id: str) -> Optional[bytes]:
        """读取文件内容，不存在返回 None"""

    @abstractmethod
    def get_info(self, storage_id: str) -> Optional[dict]:
        """获取文件元信息 {"storage_id", "filename", "size_bytes", "content_type", "created_at", "metadata"}"""

    @abstractmethod
    def delete(self, storage_id: str) -> bool:
        """删除文件，返回是否成功"""

    @abstractmethod
    def exists(self, storage_id: str) -> bool:
        """文件是否存在"""

    @abstractmethod
    def list_files(self, prefix: str = "", limit: int = 100) -> List[dict]:
        """列出文件（可选按前缀过滤），返回 get_info 列表"""


# ── TaskQueue ─────────────────────────────────────────────────────────

class TaskQueue(ABC):
    """
    异步任务队列抽象基类。

    实现：MemoryTaskQueue（内存队列，默认）
    预留：RedisTaskQueue（Redis 队列）
    """

    @abstractmethod
    def submit(self, task_id: str, task_data: dict) -> None:
        """提交任务到队列"""

    @abstractmethod
    def get_task_status(self, task_id: str) -> Optional[dict]:
        """
        查询任务状态。

        Returns:
            {"task_id": str, "status": "pending"|"processing"|"completed"|"failed",
             "result": dict|None, "error": str|None,
             "created_at": str, "updated_at": str}
        """

    @abstractmethod
    def start_worker(self, handler: Callable[[str, dict], None]) -> None:
        """
        启动后台 worker 线程。

        Args:
            handler: 处理函数，签名 handler(task_id, task_data)。
                     处理完成后应调用 update_task_status(task_id, result/error) 更新状态。
        """

    @abstractmethod
    def stop_worker(self) -> None:
        """停止后台 worker"""

    @abstractmethod
    def update_task_status(self, task_id: str, status: str, result: Optional[dict] = None, error: Optional[str] = None) -> None:
        """手动更新任务状态（供 handler 内部调用）"""
