"""Configuration management module."""

from .app_config import AppConfig
from .database_config import DatabaseConfig, MongoConfig, RedisConfig
from .browser_config import BrowserConfig, ViewportConfig, ProxyConfig
from .plugin_config import PluginConfig
from .logging_config import LoggingConfig, FileHandlerConfig, ConsoleHandlerConfig
from .config_factory import (
    ConfigFactory,
    config,
    get_app_config,
    get_database_config,
    get_browser_config,
    get_plugin_config,
    get_logging_config,
)

__all__ = [
    # Configuration classes
    "AppConfig",
    "DatabaseConfig",
    "MongoConfig",
    "RedisConfig",
    "BrowserConfig",
    "ViewportConfig",
    "ProxyConfig",
    "PluginConfig",
    "LoggingConfig",
    "FileHandlerConfig",
    "ConsoleHandlerConfig",
    # Factory and convenience functions
    "ConfigFactory",
    "config",
    "get_app_config",
    "get_database_config",
    "get_browser_config",
    "get_plugin_config",
    "get_logging_config",
]