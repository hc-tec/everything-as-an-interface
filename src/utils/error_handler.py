"""统一的错误处理和日志系统

提供统一的错误处理、日志记录和上下文捕获功能。
"""

import functools
import logging
import traceback
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union
from datetime import datetime
import asyncio

# 类型变量
F = TypeVar('F', bound=Callable[..., Any])
AsyncF = TypeVar('AsyncF', bound=Callable[..., Any])


class ErrorContext:
    """错误上下文信息"""
    
    def __init__(self, operation: str, **kwargs: Any) -> None:
        self.operation = operation
        self.context = kwargs
        self.timestamp = datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'operation': self.operation,
            'context': self.context,
            'timestamp': self.timestamp.isoformat()
        }


class ApplicationError(Exception):
    """应用程序基础异常类"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[ErrorContext] = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "APPLICATION_ERROR"
        self.context = context
        self.timestamp = datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'message': self.message,
            'error_code': self.error_code,
            'context': self.context.to_dict() if self.context else None,
            'timestamp': self.timestamp.isoformat()
        }


class ServiceError(ApplicationError):
    """服务层异常"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[ErrorContext] = None) -> None:
        super().__init__(message, error_code or "SERVICE_ERROR", context)


class NetworkError(ApplicationError):
    """网络相关异常"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[ErrorContext] = None) -> None:
        super().__init__(message, error_code or "NETWORK_ERROR", context)


class ValidationError(ApplicationError):
    """数据验证异常"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[ErrorContext] = None) -> None:
        super().__init__(message, error_code or "VALIDATION_ERROR", context)


class ConfigurationError(ApplicationError):
    """配置相关异常"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[ErrorContext] = None) -> None:
        super().__init__(message, error_code or "CONFIGURATION_ERROR", context)


class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self, logger_name: str = "error_handler") -> None:
        self.logger = logging.getLogger(logger_name)
        self._error_callbacks: Dict[Type[Exception], Callable[[Exception, ErrorContext], None]] = {}
        
    def register_error_callback(self, error_type: Type[Exception], callback: Callable[[Exception, ErrorContext], None]) -> None:
        """注册错误回调函数"""
        self._error_callbacks[error_type] = callback
        
    def handle_error(self, error: Exception, context: Optional[ErrorContext] = None) -> None:
        """处理错误"""
        # 记录错误日志
        if context:
            self.logger.error(
                f"Error in {context.operation}: {str(error)}",
                extra={
                    'error_type': type(error).__name__,
                    'context': context.to_dict(),
                    'traceback': traceback.format_exc()
                }
            )
        else:
            self.logger.error(
                f"Error: {str(error)}",
                extra={
                    'error_type': type(error).__name__,
                    'traceback': traceback.format_exc()
                }
            )
            
        # 执行注册的回调
        error_type = type(error)
        if error_type in self._error_callbacks:
            try:
                self._error_callbacks[error_type](error, context or ErrorContext("unknown"))
            except Exception as callback_error:
                self.logger.error(f"Error in error callback: {callback_error}")
                
    @contextmanager
    def error_context(self, operation: str, **kwargs: Any):
        """错误上下文管理器"""
        context = ErrorContext(operation, **kwargs)
        try:
            yield context
        except Exception as e:
            self.handle_error(e, context)
            raise
            
    def catch_and_log(self, operation: str, **context_kwargs: Any) -> Callable[[F], F]:
        """装饰器：捕获并记录错误"""
        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                context = ErrorContext(operation, function=func.__name__, **context_kwargs)
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    self.handle_error(e, context)
                    raise
            return wrapper  # type: ignore
        return decorator
        
    def catch_and_log_async(self, operation: str, **context_kwargs: Any) -> Callable[[AsyncF], AsyncF]:
        """装饰器：捕获并记录异步函数错误"""
        def decorator(func: AsyncF) -> AsyncF:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                context = ErrorContext(operation, function=func.__name__, **context_kwargs)
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    self.handle_error(e, context)
                    raise
            return wrapper  # type: ignore
        return decorator
        
    def safe_execute(self, func: Callable[[], Any], default: Any = None, operation: str = "safe_execute") -> Any:
        """安全执行函数，出错时返回默认值"""
        context = ErrorContext(operation, function=getattr(func, '__name__', 'anonymous'))
        try:
            return func()
        except Exception as e:
            self.handle_error(e, context)
            return default
            
    async def safe_execute_async(self, func: Callable[[], Any], default: Any = None, operation: str = "safe_execute_async") -> Any:
        """安全执行异步函数，出错时返回默认值"""
        context = ErrorContext(operation, function=getattr(func, '__name__', 'anonymous'))
        try:
            return await func()
        except Exception as e:
            self.handle_error(e, context)
            return default


# 全局错误处理器实例
global_error_handler = ErrorHandler("global")


# 便捷装饰器
def catch_and_log(operation: str, **context_kwargs: Any) -> Callable[[F], F]:
    """全局错误捕获装饰器"""
    return global_error_handler.catch_and_log(operation, **context_kwargs)


def catch_and_log_async(operation: str, **context_kwargs: Any) -> Callable[[AsyncF], AsyncF]:
    """全局异步错误捕获装饰器"""
    return global_error_handler.catch_and_log_async(operation, **context_kwargs)


@contextmanager
def error_context(operation: str, **kwargs: Any):
    """全局错误上下文管理器"""
    with global_error_handler.error_context(operation, **kwargs) as context:
        yield context


def safe_execute(func: Callable[[], Any], default: Any = None, operation: str = "safe_execute") -> Any:
    """全局安全执行函数"""
    return global_error_handler.safe_execute(func, default, operation)


async def safe_execute_async(func: Callable[[], Any], default: Any = None, operation: str = "safe_execute_async") -> Any:
    """全局安全执行异步函数"""
    return await global_error_handler.safe_execute_async(func, default, operation)


def setup_logging(level: Union[str, int] = logging.INFO, format_string: Optional[str] = None) -> None:
    """设置统一的日志配置"""
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 验证日志级别
    if isinstance(level, str):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if level.upper() not in valid_levels:
            raise ValueError(f"无效的日志级别: {level}")
        level = getattr(logging, level.upper())
        
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("everything-as-an-interface.log", encoding='utf-8')
        ]
    )
    
    # 设置第三方库的日志级别
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取统一配置的日志记录器"""
    return logging.getLogger(name)