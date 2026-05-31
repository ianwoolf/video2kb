"""
Memory Task Queue — 基于内存的异步任务队列（默认实现）

使用 threading.Thread + Queue 实现简单的后台 worker。
"""
from __future__ import annotations

import logging
import queue
import threading
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Optional

from shared.interfaces import TaskQueue

logger = logging.getLogger(__name__)


class MemoryTaskQueue(TaskQueue):
    """内存任务队列 — 适用于单机、低并发场景"""

    def __init__(self, max_workers: int = 1):
        self._tasks: Dict[str, dict] = {}
        self._queue: queue.Queue = queue.Queue()
        self._max_workers = max_workers
        self._workers: List[threading.Thread] = []
        self._running = False
        self._lock = threading.Lock()
        logger.info("MemoryTaskQueue: initialized (max_workers=%d)", max_workers)

    def submit(self, task_id: str, task_data: dict) -> None:
        """提交任务"""
        now = datetime.now().isoformat()
        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "task_data": task_data,
                "status": "pending",
                "result": None,
                "error": None,
                "created_at": now,
                "updated_at": now,
            }
        self._queue.put(task_id)
        logger.info("MemoryTaskQueue: submitted task %s", task_id)

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """查询任务状态"""
        with self._lock:
            return self._tasks.get(task_id)

    def update_task_status(self, task_id: str, status: str, result: Optional[dict] = None, error: Optional[str] = None) -> None:
        """手动更新任务状态"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task["status"] = status
                task["result"] = result
                task["error"] = error
                task["updated_at"] = datetime.now().isoformat()

    def start_worker(self, handler: Callable[[str, dict], None]) -> None:
        """启动后台 worker 线程"""
        self._running = True

        def _worker_loop():
            while self._running:
                try:
                    task_id = self._queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                with self._lock:
                    task = self._tasks.get(task_id)
                    if not task or task["status"] != "pending":
                        continue
                    task["status"] = "processing"
                    task["updated_at"] = datetime.now().isoformat()

                try:
                    handler(task_id, task["task_data"])
                    with self._lock:
                        if task_id in self._tasks:
                            self._tasks[task_id]["status"] = "completed"
                            self._tasks[task_id]["updated_at"] = datetime.now().isoformat()
                except Exception as e:
                    logger.error("MemoryTaskQueue: task %s failed: %s", task_id, e)
                    with self._lock:
                        if task_id in self._tasks:
                            self._tasks[task_id]["status"] = "failed"
                            self._tasks[task_id]["error"] = str(e)
                            self._tasks[task_id]["updated_at"] = datetime.now().isoformat()

        for i in range(self._max_workers):
            t = threading.Thread(target=_worker_loop, daemon=True, name=f"worker-{i}")
            t.start()
            self._workers.append(t)

        logger.info("MemoryTaskQueue: started %d worker(s)", self._max_workers)

    def stop_worker(self) -> None:
        """停止后台 worker"""
        self._running = False
        for t in self._workers:
            t.join(timeout=5.0)
        self._workers.clear()
        logger.info("MemoryTaskQueue: stopped")
