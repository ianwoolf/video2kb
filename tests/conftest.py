"""
全局测试配置 — pytest fixtures

核心机制：通过配置控制客户端指向测试服务，而非真实服务。
conftest.py 自动将服务地址环境变量指向本地 TestClient。
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest


# ── 服务地址覆盖 ──
# 测试时所有客户端指向 localhost 测试端口
# 业务代码不修改，仅通过环境变量切换
TEST_STORAGE_URL = "http://localhost:18001"
TEST_TRANSCODER_URL = "http://localhost:18002"
TEST_KB_URL = "http://localhost:18000"


@pytest.fixture(autouse=True)
def override_service_urls():
    """自动将所有服务地址指向本地测试端口（仅影响读取 env 的模块）"""
    originals = {}
    for key in ["STORAGE_URL", "TRANSCODER_URL", "DATA_SERVICE_URL"]:
        originals[key] = os.environ.get(key)
        os.environ[key] = {
            "STORAGE_URL": TEST_STORAGE_URL,
            "TRANSCODER_URL": TEST_TRANSCODER_URL,
            "DATA_SERVICE_URL": TEST_KB_URL,
        }[key]
    yield
    # 清理
    for key, val in originals.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


@pytest.fixture
def tmp_storage_dir():
    """提供临时 Storage 目录"""
    d = Path(tempfile.mkdtemp(prefix="video2kb-test-storage-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_audio_bytes():
    """提供测试用音频二进制数据（非真实音频，仅用于测试上传/下载流程）"""
    return b"FAKE_AUDIO_DATA_FOR_TESTING" * 100
