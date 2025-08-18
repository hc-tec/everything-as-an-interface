"""
工具模块 - 包含各种辅助功能
"""

from .browser import BrowserAutomation
from .async_utils import wait_until_result
from .video_downloader import BaseMediaDownloader, Mp4DownloadSession, RangeFileAssembler  # noqa: F401
from .error_handler import (
    ErrorHandler,
    ErrorContext,
    ApplicationError,
    ServiceError,
    NetworkError,
    ValidationError,
    ConfigurationError,
    global_error_handler,
    catch_and_log,
    catch_and_log_async,
    error_context,
    safe_execute,
    safe_execute_async,
    setup_logging,
    get_logger,
)

__all__ = [
    "BrowserAutomation",
    "wait_until_result",
    "BaseMediaDownloader",
    "Mp4DownloadSession",
    "RangeFileAssembler",
    "ErrorHandler",
    "ErrorContext",
    "ApplicationError",
    "ServiceError",
    "NetworkError",
    "ValidationError",
    "ConfigurationError",
    "global_error_handler",
    "catch_and_log",
    "catch_and_log_async",
    "error_context",
    "safe_execute",
    "safe_execute_async",
    "setup_logging",
    "get_logger",
]