"""
依赖注入 — 管理 service 生命周期

v0.2: 所有 service 在 main.py lifespan 中创建并存入 app.state。
此模块保留但简化，不再持有全局单例。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
