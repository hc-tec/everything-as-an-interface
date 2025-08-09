import os
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Generator, AsyncGenerator

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    创建一个会话范围的事件循环
    为所有测试提供一个共享的事件循环
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def temp_dir() -> Generator:
    """
    创建临时目录供测试使用
    测试结束后自动清理
    """
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path)

@pytest.fixture
def test_data_dir() -> str:
    """
    获取测试数据目录
    """
    base_dir = Path(__file__).parent
    data_dir = base_dir / "data"
    data_dir.mkdir(exist_ok=True)
    return str(data_dir) 