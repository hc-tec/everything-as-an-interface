"""错误处理系统使用示例

展示如何使用统一的错误处理和日志系统。
"""

import asyncio
from src.utils.error_handler import (
    catch_and_log,
    catch_and_log_async,
    error_context,
    safe_execute,
    safe_execute_async,
    ApplicationError,
    ServiceError,
    NetworkError,
    ValidationError,
)

# 设置日志
setup_logging()
logger = get_logger(__name__)


class ExampleService:
    """示例服务类"""
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.ExampleService")
    
    @catch_and_log("数据处理", service="ExampleService")
    def process_data(self, data: dict) -> dict:
        """处理数据的示例方法"""
        if not data:
            raise ValidationError("数据不能为空", error_code="EMPTY_DATA")
        
        if "required_field" not in data:
            raise ValidationError("缺少必需字段", error_code="MISSING_FIELD")
        
        # 模拟处理
        result = {"processed": True, "original": data}
        self.logger.info(f"数据处理完成: {len(data)} 个字段")
        return result
    
    @catch_and_log_async("异步网络请求", service="ExampleService")
    async def fetch_data(self, url: str) -> dict:
        """异步获取数据的示例方法"""
        if not url.startswith("http"):
            raise NetworkError("无效的URL", error_code="INVALID_URL")
        
        # 模拟网络请求
        await asyncio.sleep(0.1)
        
        if "error" in url:
            raise NetworkError("网络请求失败", error_code="REQUEST_FAILED")
        
        return {"url": url, "status": "success", "data": "mock_data"}
    
    def risky_operation(self) -> str:
        """可能出错的操作"""
        import random
        if random.random() < 0.5:
            raise ServiceError("随机错误", error_code="RANDOM_ERROR")
        return "操作成功"


def demonstrate_error_context():
    """演示错误上下文的使用"""
    logger.info("=== 演示错误上下文 ===")
    
    with error_context("用户注册", user_id="12345", operation_type="registration"):
        # 模拟一些可能出错的操作
        data = {"username": "test_user"}
        if "email" not in data:
            raise ValidationError("缺少邮箱字段", error_code="MISSING_EMAIL")


def demonstrate_safe_execution():
    """演示安全执行的使用"""
    logger.info("=== 演示安全执行 ===")
    
    service = ExampleService()
    
    # 安全执行，出错时返回默认值
    result = safe_execute(
        lambda: service.risky_operation(),
        default="默认值",
        operation="风险操作"
    )
    logger.info(f"安全执行结果: {result}")


async def demonstrate_async_safe_execution():
    """演示异步安全执行的使用"""
    logger.info("=== 演示异步安全执行 ===")
    
    service = ExampleService()
    
    # 异步安全执行
    result = await safe_execute_async(
        lambda: service.fetch_data("http://error.example.com"),
        default={"error": "请求失败"},
        operation="异步网络请求"
    )
    logger.info(f"异步安全执行结果: {result}")


def demonstrate_decorators():
    """演示装饰器的使用"""
    logger.info("=== 演示装饰器 ===")
    
    service = ExampleService()
    
    # 测试正常情况
    try:
        result = service.process_data({"required_field": "value"})
        logger.info(f"处理成功: {result}")
    except Exception as e:
        logger.error(f"处理失败: {e}")
    
    # 测试错误情况
    try:
        service.process_data({})
    except ValidationError as e:
        logger.info(f"捕获到验证错误: {e.message} (代码: {e.error_code})")


async def demonstrate_async_decorators():
    """演示异步装饰器的使用"""
    logger.info("=== 演示异步装饰器 ===")
    
    service = ExampleService()
    
    # 测试正常情况
    try:
        result = await service.fetch_data("http://example.com")
        logger.info(f"获取成功: {result}")
    except Exception as e:
        logger.error(f"获取失败: {e}")
    
    # 测试错误情况
    try:
        await service.fetch_data("invalid_url")
    except NetworkError as e:
        logger.info(f"捕获到网络错误: {e.message} (代码: {e.error_code})")


async def main():
    """主函数"""
    logger.info("开始错误处理系统演示")
    
    # 演示各种功能
    demonstrate_decorators()
    await demonstrate_async_decorators()
    
    try:
        demonstrate_error_context()
    except ValidationError as e:
        logger.info(f"演示完成，捕获到预期错误: {e.message}")
    
    demonstrate_safe_execution()
    await demonstrate_async_safe_execution()
    
    logger.info("错误处理系统演示完成")


if __name__ == "__main__":
    asyncio.run(main())