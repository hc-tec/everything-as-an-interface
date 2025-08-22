"""Configuration factory for centralized config management."""
import logging
import os
from pathlib import Path
from typing import Optional

from .app_config import AppConfig
from .database_config import DatabaseConfig
from .browser_config import BrowserConfig
from .plugin_config import PluginConfig
from .logging_config import LoggingConfig

def setup_logging(logging_config: LoggingConfig) -> None:
    """设置统一的日志配置。

    优先使用 LoggingConfig 对象提供的 dictConfig；否则退回到基本配置。"""
    # 若传入高级配置，则直接使用 dictConfig 并返回
    if logging_config is not None:
        import logging.config as _lc
        _lc.dictConfig(logging_config.get_logging_dict_config())
        return

def get_logger(name: str) -> logging.Logger:
    """获取统一配置的日志记录器"""
    return logging.getLogger(name)


class ConfigFactory:
    """Factory class for creating and managing application configurations.
    
    This class provides a centralized way to create and access all configuration
    objects used throughout the application. It supports loading environment
    variables from .env files and provides singleton-like behavior for configs.
    """
    
    @staticmethod
    def create_app_config() -> AppConfig:
        """Create a new AppConfig instance.
        
        Returns:
            AppConfig instance
        """
        return AppConfig()
    
    @staticmethod
    def create_browser_config() -> BrowserConfig:
        """Create a new BrowserConfig instance.
        
        Returns:
            BrowserConfig instance
        """
        return BrowserConfig()
    
    @staticmethod
    def create_database_config() -> DatabaseConfig:
        """Create a new DatabaseConfig instance.
        
        Returns:
            DatabaseConfig instance
        """
        return DatabaseConfig()
    
    @staticmethod
    def create_logging_config() -> LoggingConfig:
        """Create a new LoggingConfig instance.
        
        Returns:
            LoggingConfig instance
        """
        return LoggingConfig()
    
    @staticmethod
    def create_plugin_config() -> PluginConfig:
        """Create a new PluginConfig instance.
        
        Returns:
            PluginConfig instance
        """
        return PluginConfig()
    
    @staticmethod
    def create_all_configs() -> dict:
        """Create all configuration instances.
        
        Returns:
            Dictionary containing all config instances
        """
        return {
            "app": ConfigFactory.create_app_config(),
            "browser": ConfigFactory.create_browser_config(),
            "database": ConfigFactory.create_database_config(),
            "logging": ConfigFactory.create_logging_config(),
            "plugin": ConfigFactory.create_plugin_config(),
        }
    
    @staticmethod
    def load_from_file(file_path: str) -> dict:
        """Load configurations from JSON config file.
        
        Args:
            file_path: Path to JSON config file
            
        Returns:
            Dictionary containing all config instances
        """
        import json
        import json5

        
        if Path(file_path).exists():

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                try:
                    config_data = json.loads(content)
                    logging.debug("Success load config with json")
                except (json.JSONDecodeError, IOError) as e:
                    logging.warning(f"Warning: Failed to load config file {file_path} with json: {e}")
                try:
                    config_data = json5.loads(content)
                    logging.debug("Success load config with json5")
                except Exception as e:
                    logging.warning(f"Warning: Failed to load config file {file_path} with json5: {e}")
            # 将JSON配置转换为环境变量
            ConfigFactory._apply_json_config(config_data)
        
        return ConfigFactory.create_all_configs()
    
    @staticmethod
    def _get_config_value(key: str, default: str = "") -> str:
        """Get configuration value from environment variables.
        
        Args:
            key: Environment variable key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return os.getenv(key, default)
    
    @staticmethod
    def _parse_bool(value: str) -> bool:
        """Parse string value to boolean.
        
        Args:
            value: String value to parse
            
        Returns:
            Boolean value
        """
        return value.lower() in ('true', '1', 'yes', 'on')
    
    @staticmethod
    def _parse_int(value: str) -> int:
        """Parse string value to integer.
        
        Args:
            value: String value to parse
            
        Returns:
            Integer value
            
        Raises:
            ValueError: If value cannot be parsed as integer
        """
        try:
            return int(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Cannot parse '{value}' as integer") from e
    
    @staticmethod
    def _parse_list(value: str, separator: str = ",") -> list:
        """Parse string value to list.
        
        Args:
            value: String value to parse
            separator: Separator character
            
        Returns:
            List of strings
        """
        if not value:
            return []
        return [item.strip() for item in value.split(separator) if item.strip()]
    
    @staticmethod
    def _apply_json_config(config_data: dict) -> None:
        """Apply JSON configuration data to environment variables.
        
        Args:
            config_data: Dictionary containing configuration data
        """
        # 应用配置映射
        config_mapping = {
            # App config
            'app.environment': 'ENVIRONMENT',
            'app.debug': 'DEBUG',
            'app.log_level': 'LOG_LEVEL',
            'app.master_key': 'APP_MASTER_KEY',
            'app.accounts_path': 'ACCOUNTS_PATH',
            'app.data_path': 'DATA_PATH',
            
            # Browser config
            'browser.channel': 'BROWSER_CHANNEL',
            'browser.headless': 'BROWSER_HEADLESS',
            'browser.timeout_ms': 'BROWSER_TIMEOUT_MS',
            'browser.viewport.width': 'BROWSER_VIEWPORT_WIDTH',
            'browser.viewport.height': 'BROWSER_VIEWPORT_HEIGHT',
            'browser.user_agent': 'BROWSER_USER_AGENT',
            'browser.proxy.enabled': 'BROWSER_PROXY_ENABLED',
            'browser.proxy.host': 'BROWSER_PROXY_HOST',
            'browser.proxy.port': 'BROWSER_PROXY_PORT',
            'browser.proxy.username': 'BROWSER_PROXY_USERNAME',
            'browser.proxy.password': 'BROWSER_PROXY_PASSWORD',
            
            # Database config
            'database.use_mongo': 'USE_MONGO',
            'database.use_redis': 'USE_REDIS',
            'database.mongo.host': 'MONGO_HOST',
            'database.mongo.port': 'MONGO_PORT',
            'database.mongo.database': 'MONGO_DATABASE',
            'database.mongo.username': 'MONGO_USERNAME',
            'database.mongo.password': 'MONGO_PASSWORD',
            'database.redis.host': 'REDIS_HOST',
            'database.redis.port': 'REDIS_PORT',
            'database.redis.password': 'REDIS_PASSWORD',
            'database.redis.db': 'REDIS_DB',
            
            # Logging config
            'logging.level': 'LOG_LEVEL',
            'logging.format_string': 'LOG_FORMAT',
            'logging.logs_dir': 'LOGS_DIR',
            'logging.file_handler.max_bytes': 'LOG_FILE_MAX_BYTES',
            'logging.file_handler.backup_count': 'LOG_FILE_BACKUP_COUNT',
            'logging.console_handler.enabled': 'LOG_CONSOLE_ENABLED',
            
            # Plugin config
            'plugins.plugins_dir': 'PLUGINS_DIR',
            'plugins.auto_discover': 'PLUGIN_AUTO_DISCOVER',
            'plugins.enabled_plugins': 'ENABLED_PLUGINS',
            'plugins.disabled_plugins': 'DISABLED_PLUGINS',
        }
        
        def set_nested_value(data: dict, key_path: str) -> None:
            """Set environment variable from nested dictionary key."""
            keys = key_path.split('.')
            value = data
            
            try:
                for key in keys:
                    value = value[key]
                
                # 转换值为字符串
                if isinstance(value, bool):
                    env_value = str(value).lower()
                elif isinstance(value, list):
                    env_value = ','.join(str(item) for item in value)
                else:
                    env_value = str(value)
                
                # 设置环境变量
                env_key = config_mapping[key_path]
                os.environ[env_key] = env_value
                
            except (KeyError, TypeError):
                # 键不存在或类型错误，跳过
                pass
        
        # 应用所有配置映射
        for json_key in config_mapping:
            set_nested_value(config_data, json_key)
    
    @staticmethod
    def validate_config(config) -> None:
        """Validate configuration object.
        
        Args:
            config: Configuration object to validate
            
        Raises:
            ValueError: If configuration is invalid
        """
        from .app_config import AppConfig
        from .browser_config import BrowserConfig
        
        if isinstance(config, AppConfig):
            # 验证应用配置
            if not config.master_key:
                raise ValueError("主密钥不能为空")
            if not config.environment:
                raise ValueError("环境配置不能为空")
        elif isinstance(config, BrowserConfig):
            if config.timeout_ms <= 0:
                raise ValueError("超时时间必须大于 0")
    
    _instance: Optional['ConfigFactory'] = None
    _app_config: Optional[AppConfig] = None
    _database_config: Optional[DatabaseConfig] = None
    _browser_config: Optional[BrowserConfig] = None
    _plugin_config: Optional[PluginConfig] = None
    _logging_config: Optional[LoggingConfig] = None
    
    def __new__(cls) -> 'ConfigFactory':
        """Ensure singleton behavior."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the config factory."""
        if not hasattr(self, '_initialized'):
            self._load_config_file()
            self._initialized = True
    
    def _load_config_file(self) -> None:
        """Load configuration from config.json file if it exists."""
        import json
        
        # Try to find config.json file in project root
        config_file = Path.cwd() / 'config.json'
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 将JSON配置转换为环境变量
                self._apply_json_config(config_data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load config.json: {e}")
        else:
            # Try parent directories
            current = Path.cwd()
            for parent in current.parents:
                config_file = parent / 'config.json'
                if config_file.exists():
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                        
                        # 将JSON配置转换为环境变量
                        self._apply_json_config(config_data)
                        break
                    except (json.JSONDecodeError, IOError) as e:
                        print(f"Warning: Failed to load config.json from {config_file}: {e}")
    
    @property
    def app(self) -> AppConfig:
        """Get application configuration.
        
        Returns:
            AppConfig instance
        """
        if self._app_config is None:
            self._app_config = AppConfig()
        return self._app_config
    
    @property
    def database(self) -> DatabaseConfig:
        """Get database configuration.
        
        Returns:
            DatabaseConfig instance
        """
        if self._database_config is None:
            self._database_config = DatabaseConfig()
        return self._database_config
    
    @property
    def browser(self) -> BrowserConfig:
        """Get browser configuration.
        
        Returns:
            BrowserConfig instance
        """
        if self._browser_config is None:
            self._browser_config = BrowserConfig()
        return self._browser_config
    
    @property
    def plugin(self) -> PluginConfig:
        """Get plugin configuration.
        
        Returns:
            PluginConfig instance
        """
        if self._plugin_config is None:
            self._plugin_config = PluginConfig()
        return self._plugin_config
    
    @property
    def logging(self) -> LoggingConfig:
        """Get logging configuration.
        
        Returns:
            LoggingConfig instance
        """
        if self._logging_config is None:
            self._logging_config = LoggingConfig()
        return self._logging_config
    
    def reload_all(self) -> None:
        """Reload all configurations.
        
        This will force recreation of all config objects on next access,
        useful for picking up configuration changes.
        """
        self._app_config = None
        self._database_config = None
        self._browser_config = None
        self._plugin_config = None
        self._logging_config = None
        self._load_config_file()
    
    def get_env_summary(self) -> dict:
        """Get a summary of current environment configuration.
        
        Returns:
            Dictionary containing configuration summary
        """
        return {
            "environment": self.app.environment,
            "debug": self.app.debug,
            "log_level": self.app.log_level,
            "mongo_enabled": self.database.use_mongo,
            "redis_enabled": self.database.use_redis,
            "browser_headless": self.browser.headless,
            "browser_channel": self.browser.channel,
            "enabled_plugins": self.plugin.enabled_plugins,
            "auto_discover_plugins": self.plugin.auto_discover,
        }

