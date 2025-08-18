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


class TestConfigFactory:
    """配置工厂测试类"""
    
    def test_create_app_config_default(self):
        """测试创建默认应用配置"""
        config = ConfigFactory.create_app_config()
        
        assert isinstance(config, AppConfig)
        assert config.app_name == "everything-as-interface"
        assert config.version == "0.1.0"
        assert config.debug is False
        assert config.host == "localhost"
        assert config.port == 8000
    
    @patch.dict(os.environ, {
        "APP_NAME": "test-app",
        "APP_VERSION": "1.0.0",
        "DEBUG": "true",
        "HOST": "0.0.0.0",
        "PORT": "9000"
    })
    def test_create_app_config_from_env(self):
        """测试从环境变量创建应用配置"""
        config = ConfigFactory.create_app_config()
        
        assert config.app_name == "test-app"
        assert config.version == "1.0.0"
        assert config.debug is True
        assert config.host == "0.0.0.0"
        assert config.port == 9000
    
    def test_create_browser_config_default(self):
        """测试创建默认浏览器配置"""
        config = ConfigFactory.create_browser_config()
        
        assert isinstance(config, BrowserConfig)
        assert config.browser_type == "chromium"
        assert config.headless is True
        assert config.timeout == 30000
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
    
    @patch.dict(os.environ, {
        "BROWSER_TYPE": "firefox",
        "HEADLESS": "false",
        "BROWSER_TIMEOUT": "60000",
        "VIEWPORT_WIDTH": "1366",
        "VIEWPORT_HEIGHT": "768"
    })
    def test_create_browser_config_from_env(self):
        """测试从环境变量创建浏览器配置"""
        config = ConfigFactory.create_browser_config()
        
        assert config.browser_type == "firefox"
        assert config.headless is False
        assert config.timeout == 60000
        assert config.viewport_width == 1366
        assert config.viewport_height == 768
    
    def test_create_database_config_default(self):
        """测试创建默认数据库配置"""
        config = ConfigFactory.create_database_config()
        
        assert isinstance(config, DatabaseConfig)
        assert config.database_type == "sqlite"
        assert "memory" in config.database_url or "sqlite" in config.database_url
        assert config.pool_size == 5
        assert config.max_overflow == 10
    
    @patch.dict(os.environ, {
        "DATABASE_TYPE": "postgresql",
        "DATABASE_URL": "postgresql://user:pass@localhost/db",
        "DB_POOL_SIZE": "20",
        "DB_MAX_OVERFLOW": "30"
    })
    def test_create_database_config_from_env(self):
        """测试从环境变量创建数据库配置"""
        config = ConfigFactory.create_database_config()
        
        assert config.database_type == "postgresql"
        assert config.database_url == "postgresql://user:pass@localhost/db"
        assert config.pool_size == 20
        assert config.max_overflow == 30
    
    def test_create_logging_config_default(self):
        """测试创建默认日志配置"""
        config = ConfigFactory.create_logging_config()
        
        assert isinstance(config, LoggingConfig)
        assert config.level == "INFO"
        assert config.format_string is not None
        assert config.file_path is not None
        assert config.max_file_size == 10 * 1024 * 1024  # 10MB
        assert config.backup_count == 5
    
    @patch.dict(os.environ, {
        "LOG_LEVEL": "DEBUG",
        "LOG_FORMAT": "%(name)s - %(message)s",
        "LOG_FILE": "/tmp/test.log",
        "LOG_MAX_SIZE": "20971520",  # 20MB
        "LOG_BACKUP_COUNT": "10"
    })
    def test_create_logging_config_from_env(self):
        """测试从环境变量创建日志配置"""
        config = ConfigFactory.create_logging_config()
        
        assert config.level == "DEBUG"
        assert config.format_string == "%(name)s - %(message)s"
        assert config.file_path == "/tmp/test.log"
        assert config.max_file_size == 20971520
        assert config.backup_count == 10
    
    def test_create_plugin_config_default(self):
        """测试创建默认插件配置"""
        config = ConfigFactory.create_plugin_config()
        
        assert isinstance(config, PluginConfig)
        assert config.plugin_dir is not None
        assert config.auto_load is True
        assert config.enabled_plugins == []
        assert config.disabled_plugins == []
    
    @patch.dict(os.environ, {
        "PLUGIN_DIR": "/custom/plugins",
        "PLUGIN_AUTO_LOAD": "false",
        "ENABLED_PLUGINS": "plugin1,plugin2,plugin3",
        "DISABLED_PLUGINS": "plugin4,plugin5"
    })
    def test_create_plugin_config_from_env(self):
        """测试从环境变量创建插件配置"""
        config = ConfigFactory.create_plugin_config()
        
        assert config.plugin_dir == "/custom/plugins"
        assert config.auto_load is False
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
        "APP_NAME": "test-all",
        "BROWSER_TYPE": "webkit",
        "DATABASE_TYPE": "mysql",
        "LOG_LEVEL": "WARNING",
        "PLUGIN_AUTO_LOAD": "false"
    })
    def test_create_all_configs_from_env(self):
        """测试从环境变量创建所有配置"""
        configs = ConfigFactory.create_all_configs()
        
        assert configs["app"].app_name == "test-all"
        assert configs["browser"].browser_type == "webkit"
        assert configs["database"].database_type == "mysql"
        assert configs["logging"].level == "WARNING"
        assert configs["plugin"].auto_load is False
    
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
APP_NAME=file-test-app
APP_VERSION=2.0.0
DEBUG=true
BROWSER_TYPE=firefox
HEADLESS=false
DATABASE_TYPE=postgresql
LOG_LEVEL=ERROR
PLUGIN_AUTO_LOAD=false
"""
        env_file.write_text(env_content)
        
        configs = ConfigFactory.load_from_file(str(env_file))
        
        assert configs["app"].app_name == "file-test-app"
        assert configs["app"].version == "2.0.0"
        assert configs["app"].debug is True
        assert configs["browser"].browser_type == "firefox"
        assert configs["browser"].headless is False
        assert configs["database"].database_type == "postgresql"
        assert configs["logging"].level == "ERROR"
        assert configs["plugin"].auto_load is False
    
    def test_validate_config_valid(self):
        """测试验证有效配置"""
        config = ConfigFactory.create_app_config()
        
        # 应该不抛出异常
        ConfigFactory.validate_config(config)
    
    def test_validate_config_invalid_port(self):
        """测试验证无效端口配置"""
        config = AppConfig(
            app_name="test",
            version="1.0.0",
            debug=False,
            host="localhost",
            port=-1  # 无效端口
        )
        
        with pytest.raises(ValueError, match="端口号必须在 1-65535 范围内"):
            ConfigFactory.validate_config(config)
    
    def test_validate_config_invalid_timeout(self):
        """测试验证无效超时配置"""
        config = BrowserConfig(
            browser_type="chromium",
            headless=True,
            timeout=-1000,  # 无效超时
            viewport_width=1920,
            viewport_height=1080
        )
        
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