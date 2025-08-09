import os
import pytest
import tempfile
import shutil
import importlib
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock

from src.core.plugin_manager import PluginManager
from src.plugins.base import BasePlugin

class MockPlugin(BasePlugin):
    """测试用插件类"""
    PLUGIN_ID = "mock_plugin"
    PLUGIN_NAME = "Mock Plugin"
    PLUGIN_DESCRIPTION = "A mock plugin for testing"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_AUTHOR = "Tester"
    
    def start(self) -> bool:
        return True
        
    def stop(self) -> bool:
        return True
        
    async def fetch(self) -> Dict[str, Any]:
        return {"success": True, "data": "mock_data"}

class TestPluginManager:
    """插件管理器测试类"""
    
    @pytest.fixture
    def temp_plugin_dir(self):
        """创建临时插件目录"""
        temp_dir = tempfile.mkdtemp()
        # 创建一个测试插件文件
        plugin_code = """
from src.plugins.base import BasePlugin

class TestPlugin(BasePlugin):
    PLUGIN_ID = "test_plugin"
    PLUGIN_NAME = "Test Plugin"
    PLUGIN_DESCRIPTION = "A plugin for testing"
    PLUGIN_VERSION = "0.1.0"
    PLUGIN_AUTHOR = "Tester"
    
    def start(self):
        return True
        
    def stop(self):
        return True
        
    async def fetch(self):
        return {"success": True, "data": "test_data"}
"""
        plugin_file = os.path.join(temp_dir, "test_plugin.py")
        with open(plugin_file, "w") as f:
            f.write(plugin_code)
            
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def plugin_manager(self, monkeypatch):
        """创建带有内存测试插件的PluginManager实例"""
        # 模拟模块导入，使插件发现机制能够找到MockPlugin
        def mock_import_module(name, package=None):
            if name == "src.plugins.mock":
                mock_module = MagicMock()
                mock_module.MockPlugin = MockPlugin
                return mock_module
            return importlib.import_module(name, package)
            
        monkeypatch.setattr(importlib, 'import_module', mock_import_module)
        
        # 模拟文件系统操作，使插件发现机制能够找到mock插件文件
        def mock_glob(*args, **kwargs):
            return [Path("mock.py")]
            
        monkeypatch.setattr(Path, 'glob', mock_glob)
        
        manager = PluginManager()
        return manager
    
    def test_init(self, plugin_manager):
        """测试初始化"""
        assert plugin_manager.plugins is not None
        assert plugin_manager.plugin_instances is not None
        # 验证是否发现了模拟插件
        assert "mock_plugin" in plugin_manager.plugins
    
    def test_get_plugin_class(self, plugin_manager):
        """测试获取插件类"""
        # 获取存在的插件
        plugin_class = plugin_manager.get_plugin_class("mock_plugin")
        assert plugin_class is MockPlugin
        
        # 获取不存在的插件
        plugin_class = plugin_manager.get_plugin_class("nonexistent_plugin")
        assert plugin_class is None
    
    def test_get_all_plugins(self, plugin_manager):
        """测试获取所有插件"""
        plugins = plugin_manager.get_all_plugins()
        assert "mock_plugin" in plugins
        assert plugins["mock_plugin"] is MockPlugin
    
    def test_instantiate_plugin(self, plugin_manager):
        """测试实例化插件"""
        # 实例化存在的插件
        instance = plugin_manager.instantiate_plugin("mock_plugin")
        assert isinstance(instance, MockPlugin)
        assert plugin_manager.plugin_instances["mock_plugin"] is instance
        
        # 实例化不存在的插件应该抛出异常
        with pytest.raises(ValueError):
            plugin_manager.instantiate_plugin("nonexistent_plugin")
    
    def test_get_plugin_instance(self, plugin_manager):
        """测试获取插件实例"""
        # 首先实例化一个插件
        instance1 = plugin_manager.instantiate_plugin("mock_plugin")
        
        # 获取该实例
        instance2 = plugin_manager.get_plugin_instance("mock_plugin")
        assert instance1 is instance2
        
        # 获取不存在的实例
        instance3 = plugin_manager.get_plugin_instance("nonexistent_plugin")
        assert instance3 is None
    
    def test_reload_plugins(self, plugin_manager):
        """测试重新加载插件"""
        # 先实例化一个插件
        instance = plugin_manager.instantiate_plugin("mock_plugin")
        
        # 重新加载插件
        plugin_manager.reload_plugins()
        
        # 验证插件类仍然存在但实例已清除
        assert "mock_plugin" in plugin_manager.plugins
        assert "mock_plugin" not in plugin_manager.plugin_instances
        
    def test_discover_plugins_with_real_dir(self, temp_plugin_dir):
        """使用真实目录测试插件发现机制"""
        # 创建一个指向临时目录的插件管理器
        manager = PluginManager([temp_plugin_dir])
        
        # 验证是否发现了测试插件
        assert "test_plugin" in manager.plugins 