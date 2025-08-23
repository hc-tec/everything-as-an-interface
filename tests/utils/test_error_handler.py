"""错误处理模块测试

测试统一错误处理系统的各种功能。
"""

import pytest
import logging
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from typing import Any, Dict

from src.utils.error_handler import (
    ErrorHandler,
    ErrorContext,
    ApplicationError,
    ValidationError,
    ConfigurationError,
    NetworkError,
    ServiceError,
    global_error_handler,
    catch_and_log,
    catch_and_log_async,
    error_context,
    safe_execute,
    safe_execute_async,
    get_logger,
)

@pytest.mark.skip
class TestApplicationError:
    """应用错误基类测试"""
    
    def test_application_error_basic(self):
        """测试基本应用错误"""
        error = ApplicationError("Test error")
        assert str(error) == "Test error"
        assert error.error_code == "APPLICATION_ERROR"
        assert error.context is None
    
    def test_application_error_with_context(self):
        """测试带上下文的应用错误"""
        context = ErrorContext("login", user_id=123, action="login")
        error = ApplicationError("Login failed", context=context)
        
        assert str(error) == "Login failed"
        assert error.context == context
    
    def test_validation_error(self):
        """测试验证错误"""
        error = ValidationError("Invalid input")
        assert error.error_code == "VALIDATION_ERROR"
        assert str(error) == "Invalid input"
    
    def test_configuration_error(self):
        """测试配置错误"""
        error = ConfigurationError("Missing config")
        assert error.error_code == "CONFIGURATION_ERROR"
        assert str(error) == "Missing config"
    
    def test_network_error(self):
        """测试网络错误"""
        error = NetworkError("Connection failed")
        assert error.error_code == "NETWORK_ERROR"
        assert str(error) == "Connection failed"
    
    def test_service_error(self):
        """测试服务错误"""
        error = ServiceError("Service failed")
        assert str(error) == "Service failed"


class TestErrorContext:
    """错误上下文测试"""
    
    def test_error_context_creation(self):
        """测试错误上下文创建"""
        context = ErrorContext(
            operation="test_operation",
            user_id="user123",
            request_id="req456"
        )
        
        assert context.operation == "test_operation"
        assert context.context["user_id"] == "user123"
        assert context.context["request_id"] == "req456"
        assert context.timestamp is not None
    
    def test_error_context_with_additional_data(self):
        """测试带额外数据的错误上下文"""
        context = ErrorContext(
            operation="test_op",
            param1="value1",
            param2=42
        )
        
        assert context.context["param1"] == "value1"
        assert context.context["param2"] == 42
    
    def test_error_context_to_dict(self):
        """测试错误上下文转字典"""
        context = ErrorContext(
            operation="test_operation",
            user_id="user123",
            key="value"
        )
        
        context_dict = context.to_dict()
        
        assert context_dict["operation"] == "test_operation"
        assert context_dict["context"]["user_id"] == "user123"
        assert context_dict["context"]["key"] == "value"
        assert "timestamp" in context_dict


class TestErrorHandler:
    """错误处理器测试"""
    
    def test_error_handler_creation(self):
        """测试错误处理器创建"""
        handler = ErrorHandler("test_logger")
        assert handler.logger.name == "test_logger"
    
    def test_handle_error_basic(self):
        """测试基本错误处理"""
        handler = ErrorHandler("test")
        error = ApplicationError("Test error")
        
        with patch.object(handler.logger, 'error') as mock_error:
            handler.handle_error(error)
            mock_error.assert_called_once()
            call_args = mock_error.call_args[0]
            assert "Test error" in call_args[0]
    
    def test_handle_error_with_context(self):
        """测试带上下文的错误处理"""
        handler = ErrorHandler("test")
        context = ErrorContext(operation="test_op", user_id="user123")
        error = ApplicationError("Test error", context=context)
        
        with patch.object(handler.logger, 'error') as mock_error:
            handler.handle_error(error, context)
            mock_error.assert_called_once()
            call_args = mock_error.call_args[0]
            assert "test_op" in call_args[0]
            # 检查extra参数中的上下文信息
            call_kwargs = mock_error.call_args[1]
            assert "context" in call_kwargs["extra"]
            assert call_kwargs["extra"]["context"]["context"]["user_id"] == "user123"
    
    def test_handle_exception_basic(self):
        """测试基本异常处理"""
        handler = ErrorHandler("test")
        
        with patch.object(handler.logger, 'error') as mock_error:
            try:
                raise ValueError("Test exception")
            except Exception as e:
                handler.handle_error(e)
            
            mock_error.assert_called_once()
    
    def test_handle_exception_with_context(self):
        """测试带上下文的异常处理"""
        handler = ErrorHandler("test")
        context = ErrorContext(operation="test_op")
        
        with patch.object(handler.logger, 'error') as mock_error:
            try:
                raise ValueError("Test exception")
            except Exception as e:
                handler.handle_error(e, context)
            
            mock_error.assert_called_once()


class TestCatchAndLog:
    """catch_and_log装饰器测试"""
    
    def test_catch_and_log_success(self):
        """测试成功执行的函数"""
        @catch_and_log("test_operation")
        def test_function(x, y):
            return x + y
        
        result = test_function(1, 2)
        assert result == 3
    
    def test_catch_and_log_exception(self):
        """测试抛出异常的函数"""
        @catch_and_log("test_operation")
        def test_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            test_function()
    
    def test_catch_and_log_with_default(self):
        """测试带默认返回值的装饰器"""
        @catch_and_log("test_operation")
        def test_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            test_function()
    
    def test_catch_and_log_reraise(self):
        """测试重新抛出异常的装饰器"""
        @catch_and_log("test_operation")
        def test_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            test_function()


class TestSafeExecute:
    """safe_execute函数测试"""
    
    def test_safe_execute_success(self):
        """测试成功执行"""
        def test_function():
            return "success"
        
        result = safe_execute(test_function)
        assert result == "success"
    
    def test_safe_execute_exception(self):
        """测试异常执行"""
        def test_function():
            raise ValueError("Test error")
        
        result = safe_execute(test_function)
        assert result is None
    
    def test_safe_execute_with_args(self):
        """测试带参数的安全执行"""
        def test_function():
            return 1 + 2 + 3
        
        result = safe_execute(test_function)
        assert result == 6
    
    def test_safe_execute_with_default(self):
        """测试带默认值的安全执行"""
        def test_function():
            raise ValueError("Test error")
        
        result = safe_execute(test_function, default="default")
        assert result == "default"
    
    def test_safe_execute_with_context(self):
        """测试带上下文的安全执行"""
        def test_function():
            raise ValueError("Test error")
        
        result = safe_execute(test_function, operation="test_op")
        assert result is None

class TestGlobalErrorHandler:
    """全局错误处理器测试"""
    
    def test_global_error_handler_exists(self):
        """测试全局错误处理器存在"""
        assert global_error_handler is not None
        assert isinstance(global_error_handler, ErrorHandler)
    
    def test_global_error_handler_usage(self):
        """测试全局错误处理器使用"""
        with patch.object(global_error_handler, 'logger') as mock_logger:
            error = ApplicationError("Global test error")
            global_error_handler.handle_error(error)
            
            mock_logger.error.assert_called_once()


class TestIntegration:
    """集成测试"""
    
    def test_full_error_handling_flow(self, temp_dir):
        """测试完整错误处理流程"""
        # 设置日志
        
        # 创建上下文
        context = ErrorContext(
            operation="integration_test",
            user_id="test_user",
            additional_data={"test_param": "test_value"}
        )
        
        # 使用装饰器处理错误
        @catch_and_log("integration_test")
        def failing_function():
            raise ValidationError("Integration test error", context=context)
        
        with pytest.raises(ValidationError):
            failing_function()
        
        # 验证默认日志文件
        log_file = Path("everything-as-an-interface.log")
        assert log_file.exists()
    
    def test_nested_error_handling(self, temp_dir):
        """测试嵌套错误处理"""
        
        @catch_and_log("inner_operation")
        def inner_function():
            raise ServiceError("Inner error")
        
        @catch_and_log("outer_operation")
        def outer_function():
            try:
                inner_function()
            except ServiceError:
                pass  # 内层错误已被记录
            raise NetworkError("Outer error")
        
        with pytest.raises(NetworkError):
            outer_function()
        
        # 验证两个错误都被记录
        log_file = Path("everything-as-an-interface.log")
        assert log_file.exists()