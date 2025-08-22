"""配置工厂测试模块

测试配置工厂的各种功能，包括环境变量加载、配置验证等。
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from typing import Dict, Any

from src.config.config_factory import ConfigFactory
from src.config.app_config import AppConfig
from src.config.browser_config import BrowserConfig
from src.config.database_config import DatabaseConfig
from src.config.logging_config import LoggingConfig
from src.config.plugin_config import PluginConfig

@pytest.mark.skip
class TestConfigFactory:
    """配置工厂测试类"""
    
    def test_create_app_config_default(self):
        """测试创建默认应用配置"""
        config = ConfigFactory.create_app_config()
        
        assert isinstance(config, AppConfig)
        assert config.environment == "development"
        assert config.debug is False
        assert config.log_level == "INFO"
        assert config.master_key == "default-dev-key"
    
    @patch.dict(os.environ, {
        "ENVIRONMENT": "test",
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG",
        "APP_MASTER_KEY": "test-key"
    })
    def test_create_app_config_from_env(self):
        """测试从环境变量创建应用配置"""
        config = ConfigFactory.create_app_config()
        
        assert config.environment == "test"
        assert config.debug is True
        assert config.log_level == "DEBUG"
        assert config.master_key == "test-key"
    
    def test_create_browser_config_default(self):
        """测试创建默认浏览器配置"""
        config = ConfigFactory.create_browser_config()
        
        assert isinstance(config, BrowserConfig)
        assert config.channel == "msedge"
        assert config.headless is False
        assert config.timeout_ms == 30000
        assert config.viewport.width == 1280
        assert config.viewport.height == 800
    
    @patch.dict(os.environ, {
        "BROWSER_CHANNEL": "chrome",
        "BROWSER_HEADLESS": "true",
        "BROWSER_TIMEOUT_MS": "60000",
        "BROWSER_VIEWPORT_WIDTH": "1366",
        "BROWSER_VIEWPORT_HEIGHT": "768"
    })
    def test_create_browser_config_from_env(self):
        """测试从环境变量创建浏览器配置"""
        config = ConfigFactory.create_browser_config()
        
        assert config.channel == "chrome"
        assert config.headless is True
        assert config.timeout_ms == 60000
        assert config.viewport.width == 1366
        assert config.viewport.height == 768
    
    def test_create_database_config_default(self):
        """测试创建默认数据库配置"""
        config = ConfigFactory.create_database_config()
        
        assert isinstance(config, DatabaseConfig)
        assert config.use_mongo is True
        assert config.use_redis is True
        assert config.mongo.host == "localhost"
        assert config.mongo.port == 27017
        assert config.redis.host == "localhost"
        assert config.redis.port == 6379
    
    @patch.dict(os.environ, {
        "USE_MONGO": "false",
        "USE_REDIS": "false",
        "MONGO_HOST": "mongo.example.com",
        "MONGO_PORT": "27018",
        "REDIS_HOST": "redis.example.com",
        "REDIS_PORT": "6380"
    })
    def test_create_database_config_from_env(self):
        """测试从环境变量创建数据库配置"""
        config = ConfigFactory.create_database_config()
        
        assert config.use_mongo is False
        assert config.use_redis is False
        assert config.mongo.host == "mongo.example.com"
        assert config.mongo.port == 27018
        assert config.redis.host == "redis.example.com"
        assert config.redis.port == 6380
    
    def test_create_logging_config_default(self):
        """测试创建默认日志配置"""
        config = ConfigFactory.create_logging_config()
        
        assert isinstance(config, LoggingConfig)
        assert config.level == "INFO"
        assert config.format_string is not None
        assert config.log_file_path is not None
        assert config.file_handler.max_bytes == 10485760  # 10MB
        assert config.file_handler.backup_count == 5
    
    @patch.dict(os.environ, {
        "LOG_LEVEL": "DEBUG",
        "LOG_FORMAT": "%(name)s - %(message)s",
        "LOGS_DIR": "D:\\tmp\\logs",
        "LOG_FILE_MAX_BYTES": "20971520",  # 20MB
        "LOG_FILE_BACKUP_COUNT": "10"
    })
    def test_create_logging_config_from_env(self):
        """测试从环境变量创建日志配置"""
        config = ConfigFactory.create_logging_config()
        
        assert config.level == "DEBUG"
        assert config.format_string == "%(name)s - %(message)s"
        assert str(config.logs_dir) == "D:\\tmp\\logs"
        assert config.file_handler.max_bytes == 20971520
        assert config.file_handler.backup_count == 10
    
    def test_create_plugin_config_default(self):
        """测试创建默认插件配置"""
        config = ConfigFactory.create_plugin_config()
        
        assert isinstance(config, PluginConfig)
        assert config.plugins_dir is not None
        assert config.auto_discover is True
        assert config.enabled_plugins == ["xiaohongshu_v2"]
        assert config.disabled_plugins == []
    
    @patch.dict(os.environ, {
        "PLUGINS_DIR": "D:\\custom\\plugins",
        "PLUGIN_AUTO_DISCOVER": "false",
        "ENABLED_PLUGINS": "plugin1,plugin2,plugin3",
        "DISABLED_PLUGINS": "plugin4,plugin5"
    })
    def test_create_plugin_config_from_env(self):
        """测试从环境变量创建插件配置"""
        config = ConfigFactory.create_plugin_config()
        
        assert str(config.plugins_dir) == "D:\\custom\\plugins"
        assert config.auto_discover is False
        assert config.enabled_plugins == ["plugin1", "plugin2", "plugin3"]
        assert config.disabled_plugins == ["plugin4", "plugin5"]
    
    def test_create_all_configs(self):
        """测试创建所有配置"""
        configs = ConfigFactory.create_all_configs()
        
        assert "app" in configs
        assert "browser" in configs
        assert "database" in configs
        assert "logging" in configs
        assert "plugin" in configs
        
        assert isinstance(configs["app"], AppConfig)
        assert isinstance(configs["browser"], BrowserConfig)
        assert isinstance(configs["database"], DatabaseConfig)
        assert isinstance(configs["logging"], LoggingConfig)
        assert isinstance(configs["plugin"], PluginConfig)
    
    @patch.dict(os.environ, {
        "ENVIRONMENT": "test-all",
        "BROWSER_CHANNEL": "webkit",
        "USE_MONGO": "false",
        "LOG_LEVEL": "WARNING",
        "PLUGIN_AUTO_DISCOVER": "false"
    })
    def test_create_all_configs_from_env(self):
        """测试从环境变量创建所有配置"""
        configs = ConfigFactory.create_all_configs()
        
        assert configs["app"].environment == "test-all"
        assert configs["browser"].channel == "webkit"
        assert configs["database"].use_mongo is False
        assert configs["logging"].level == "WARNING"
        assert configs["plugin"].auto_discover is False
    
    def test_load_from_file_not_exists(self):
        """测试加载不存在的配置文件"""
        non_existent_file = "/path/to/non/existent/file.env"
        
        # 应该不抛出异常，而是使用默认配置
        configs = ConfigFactory.load_from_file(non_existent_file)
        
        assert "app" in configs
        assert isinstance(configs["app"], AppConfig)
    
    def test_load_from_file_exists(self, temp_dir):
        """测试加载存在的配置文件"""
        env_file = Path(temp_dir) / ".env"
        env_content = """
ENVIRONMENT=file-test-env
APP_MASTER_KEY=file-test-key
DEBUG=true
BROWSER_CHANNEL=firefox
BROWSER_HEADLESS=true
USE_MONGO=false
LOG_LEVEL=ERROR
PLUGIN_AUTO_DISCOVER=false
"""
        env_file.write_text(env_content)
        
        configs = ConfigFactory.load_from_file(str(env_file))
        
        assert configs["app"].environment == "file-test-env"
        assert configs["app"].master_key == "file-test-key"
        assert configs["app"].debug is True
        assert configs["browser"].channel == "firefox"
        assert configs["browser"].headless is True
        assert configs["database"].use_mongo is False
        assert configs["logging"].level == "ERROR"
        assert configs["plugin"].auto_discover is False
    
    def test_validate_config_valid(self):
        """测试验证有效配置"""
        # 创建一个有效的模拟配置对象
        class MockValidAppConfig:
            def __init__(self):
                self.port = 8080  # 有效端口
        
        config = MockValidAppConfig()
        
        # 应该不抛出异常
        ConfigFactory.validate_config(config)
    
    def test_validate_config_invalid_port(self):
        """测试验证无效端口配置"""
        from src.config.app_config import AppConfig
        
        # 创建一个模拟的配置对象来测试端口验证
        class MockAppConfig(AppConfig):
            def __init__(self):
                super().__init__()
                self.port = -1  # 无效端口
        
        config = MockAppConfig()
        
        with pytest.raises(ValueError, match="端口号必须在 1-65535 范围内"):
            ConfigFactory.validate_config(config)
    
    def test_validate_config_invalid_timeout(self):
        """测试验证无效超时配置"""
        from src.config.browser_config import BrowserConfig
        
        # 创建一个模拟的配置对象来测试超时验证
        class MockBrowserConfig(BrowserConfig):
            def __init__(self):
                super().__init__()
                self.timeout = -1000  # 无效超时
        
        config = MockBrowserConfig()
        
        with pytest.raises(ValueError, match="超时时间必须大于 0"):
            ConfigFactory.validate_config(config)
    
    def test_get_config_value_exists(self):
        """测试获取存在的配置值"""
        with patch.dict(os.environ, {"TEST_KEY": "test_value"}):
            value = ConfigFactory._get_config_value("TEST_KEY", "default")
            assert value == "test_value"
    
    def test_get_config_value_not_exists(self):
        """测试获取不存在的配置值"""
        # 确保环境变量不存在
        if "NON_EXISTENT_KEY" in os.environ:
            del os.environ["NON_EXISTENT_KEY"]
        
        value = ConfigFactory._get_config_value("NON_EXISTENT_KEY", "default_value")
        assert value == "default_value"
    
    def test_parse_bool_true_values(self):
        """测试解析布尔值 - 真值"""
        true_values = ["true", "True", "TRUE", "1", "yes", "Yes", "YES"]
        
        for value in true_values:
            assert ConfigFactory._parse_bool(value) is True
    
    def test_parse_bool_false_values(self):
        """测试解析布尔值 - 假值"""
        false_values = ["false", "False", "FALSE", "0", "no", "No", "NO", ""]
        
        for value in false_values:
            assert ConfigFactory._parse_bool(value) is False
    
    def test_parse_int_valid(self):
        """测试解析有效整数"""
        assert ConfigFactory._parse_int("123") == 123
        assert ConfigFactory._parse_int("-456") == -456
        assert ConfigFactory._parse_int("0") == 0
    
    def test_parse_int_invalid(self):
        """测试解析无效整数"""
        with pytest.raises(ValueError):
            ConfigFactory._parse_int("not_a_number")
        
        with pytest.raises(ValueError):
            ConfigFactory._parse_int("12.34")
    
    def test_parse_list_comma_separated(self):
        """测试解析逗号分隔的列表"""
        result = ConfigFactory._parse_list("item1,item2,item3")
        assert result == ["item1", "item2", "item3"]
    
    def test_parse_list_with_spaces(self):
        """测试解析带空格的列表"""
        result = ConfigFactory._parse_list("item1, item2 , item3")
        assert result == ["item1", "item2", "item3"]
    
    def test_parse_list_empty(self):
        """测试解析空列表"""
        result = ConfigFactory._parse_list("")
        assert result == []
        
        result = ConfigFactory._parse_list("   ")
        assert result == []
    
    def test_parse_list_single_item(self):
        """测试解析单项列表"""
        result = ConfigFactory._parse_list("single_item")
        assert result == ["single_item"]