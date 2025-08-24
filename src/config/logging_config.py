"""Logging configuration management."""
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional

from settings import PROJECT_ROOT


@dataclass
class FileHandlerConfig:
    """File handler configuration for logging.
    
    Attributes:
        filename: Log file name
        max_bytes: Maximum file size in bytes before rotation
        backup_count: Number of backup files to keep
        encoding: File encoding
    """
    
    filename: str = "app.log"
    max_bytes: int = field(default_factory=lambda: int(os.getenv("LOG_FILE_MAX_BYTES", "10485760")))  # 10MB
    backup_count: int = field(default_factory=lambda: int(os.getenv("LOG_FILE_BACKUP_COUNT", "5")))
    encoding: str = "utf-8"


@dataclass
class ConsoleHandlerConfig:
    """Console handler configuration for logging.
    
    Attributes:
        enabled: Whether console logging is enabled
        level: Console logging level
        format_style: Console log format style
    """
    
    enabled: bool = field(default_factory=lambda: os.getenv("LOG_CONSOLE_ENABLED", "true").lower() == "true")
    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    format_style: str = "colored"  # colored, simple, detailed


@dataclass
class LoggingConfig:
    """Logging system configuration.
    
    Attributes:
        level: Global logging level
        logs_dir: Directory for log files
        file_handler: File handler configuration
        console_handler: Console handler configuration
        format_string: Log message format string
        date_format: Date format for log messages
        capture_warnings: Whether to capture Python warnings
        disable_existing_loggers: Whether to disable existing loggers
        logger_levels: Specific levels for named loggers
    """
    
    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    logs_dir: Path = field(default_factory=lambda: Path(os.getenv(
        "LOGS_DIR", 
        str(PROJECT_ROOT / "logs")
    )))
    file_handler: FileHandlerConfig = field(default_factory=FileHandlerConfig)
    console_handler: ConsoleHandlerConfig = field(default_factory=ConsoleHandlerConfig)
    format_string: str = field(default_factory=lambda: os.getenv(
        "LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    date_format: str = field(default_factory=lambda: os.getenv(
        "LOG_DATE_FORMAT",
        "%Y-%m-%d %H:%M:%S"
    ))
    capture_warnings: bool = field(default_factory=lambda: os.getenv("LOG_CAPTURE_WARNINGS", "true").lower() == "true")
    disable_existing_loggers: bool = field(default_factory=lambda: os.getenv("LOG_DISABLE_EXISTING", "false").lower() == "true")
    logger_levels: Dict[str, str] = field(default_factory=lambda: {
        "playwright": os.getenv("LOG_PLAYWRIGHT_LEVEL", "WARNING"),
        "urllib3": os.getenv("LOG_URLLIB3_LEVEL", "WARNING"),
        "requests": os.getenv("LOG_REQUESTS_LEVEL", "WARNING"),
        "pymongo": os.getenv("LOG_PYMONGO_LEVEL", "WARNING"),
    })
    
    def __post_init__(self) -> None:
        """Ensure logs directory exists and is absolute."""
        if not self.logs_dir.is_absolute():
            self.logs_dir = PROJECT_ROOT / self.logs_dir
        
        self.logs_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def log_file_path(self) -> Path:
        """Get full path to the log file."""
        return self.logs_dir / self.file_handler.filename
    
    def get_logging_dict_config(self) -> Dict[str, Any]:
        """Generate logging configuration dictionary for dictConfig.
        
        Returns:
            Dictionary configuration for Python's logging.config.dictConfig
        """
        config = {
            "version": 1,
            "disable_existing_loggers": self.disable_existing_loggers,
            "formatters": {
                "standard": {
                    "format": self.format_string,
                    "datefmt": self.date_format,
                },
                "detailed": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s",
                    "datefmt": self.date_format,
                },
            },
            "handlers": {},
            "loggers": {},
            "root": {
                "level": self.level,
                "handlers": [],
            },
        }
        
        # Add file handler
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": self.level,
            "formatter": "detailed",
            "filename": str(self.log_file_path),
            "maxBytes": self.file_handler.max_bytes,
            "backupCount": self.file_handler.backup_count,
            "encoding": self.file_handler.encoding,
        }
        config["root"]["handlers"].append("file")
        
        # Add console handler if enabled
        if self.console_handler.enabled:
            config["handlers"]["console"] = {
                "class": "logging.StreamHandler",
                "level": self.console_handler.level,
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            }
            config["root"]["handlers"].append("console")
        
        # Add specific logger levels
        for logger_name, level in self.logger_levels.items():
            config["loggers"][logger_name] = {
                "level": level,
                "handlers": [],
                "propagate": True,
            }
        
        return config
    
    def get_logger_level(self, logger_name: str) -> Optional[str]:
        """Get logging level for a specific logger.
        
        Args:
            logger_name: Name of the logger
            
        Returns:
            Logging level string or None if not configured
        """
        return self.logger_levels.get(logger_name)
    
    def set_logger_level(self, logger_name: str, level: str) -> None:
        """Set logging level for a specific logger.
        
        Args:
            logger_name: Name of the logger
            level: Logging level to set
        """
        self.logger_levels[logger_name] = level



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