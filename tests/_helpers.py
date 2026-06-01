"""
测试辅助工具 — sys.path 管理

各服务内部用 `from app.config import settings`，pytest 从项目根目录运行时，
需要将目标服务目录插入 sys.path 最前面，确保 `from app.xxx` 解析到正确服务。
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def push_service(service_dir: str):
    """将指定服务目录插入 sys.path[0]，确保 `from app.xxx` 解析到正确服务。

    用法：
        from tests._helpers import push_service
        push_service("storage")  # 之后 from app.config import settings 解析到 storage/app/config.py
    """
    import importlib
    svc_path = str(PROJECT_ROOT / service_dir)
    if svc_path in sys.path:
        sys.path.remove(svc_path)
    sys.path.insert(0, svc_path)
    # 清除已缓存的 app 子模块，避免解析到其他服务
    keys_to_remove = [k for k in sys.modules if k == "app" or k.startswith("app.")]
    for k in keys_to_remove:
        del sys.modules[k]
