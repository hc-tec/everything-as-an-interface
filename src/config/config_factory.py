"""Configuration factory for centralized config management."""

import os
from pathlib import Path
from typing import Optional

from .app_config import AppConfig
from .database_config import DatabaseConfig
from .browser_config import BrowserConfig
from .plugin_config import PluginConfig
from .logging_config import LoggingConfig


class ConfigFactory:
    """Factory class for creating and managing application configurations.
    
    This class provides a centralized way to create and access all configuration
    objects used throughout the application. It supports loading environment
    variables from .env files and provides singleton-like behavior for configs.
    """
    
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
            self._load_env_file()
            self._initialized = True
    
    def _load_env_file(self) -> None:
        """Load environment variables from .env file if it exists."""
        try:
            from dotenv import load_dotenv
            
            # Try to find .env file in project root
            env_file = Path.cwd() / '.env'
            if env_file.exists():
                load_dotenv(env_file)
            else:
                # Try parent directories
                current = Path.cwd()
                for parent in current.parents:
                    env_file = parent / '.env'
                    if env_file.exists():
                        load_dotenv(env_file)
                        break
        except ImportError:
            # python-dotenv not installed, skip loading .env file
            pass
    
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
        useful for picking up environment variable changes.
        """
        self._app_config = None
        self._database_config = None
        self._browser_config = None
        self._plugin_config = None
        self._logging_config = None
        self._load_env_file()
    
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


# Global config factory instance
config = ConfigFactory()


# Convenience functions for direct access
def get_app_config() -> AppConfig:
    """Get application configuration."""
    return config.app


def get_database_config() -> DatabaseConfig:
    """Get database configuration."""
    return config.database


def get_browser_config() -> BrowserConfig:
    """Get browser configuration."""
    return config.browser


def get_plugin_config() -> PluginConfig:
    """Get plugin configuration."""
    return config.plugin


def get_logging_config() -> LoggingConfig:
    """Get logging configuration."""
    return config.logging