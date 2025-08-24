"""Configuration management module."""

from .app_config import AppConfig
from .database_config import DatabaseConfig, MongoConfig, RedisConfig
from .browser_config import BrowserConfig, ViewportConfig, ProxyConfig
from .plugin_config import PluginConfig
from .logging_config import LoggingConfig, FileHandlerConfig, ConsoleHandlerConfig, setup_logging, get_logger
from .config_factory import (
    ConfigFactory
)


__all__ = [
    "setup_logging",
    "get_logger",
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
]