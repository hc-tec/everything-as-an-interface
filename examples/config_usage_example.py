#!/usr/bin/env python3
"""配置系统使用示例

这个示例展示了如何使用新的配置管理系统来初始化和配置应用程序。
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src import EverythingAsInterface
from src.config import (
    ConfigFactory,
)


def demonstrate_config_usage():
    """演示配置系统的使用方法"""
    print("=== 配置系统使用示例 ===")
    print()
    
    # 方法1: 使用便捷函数直接获取配置
    print("1. 使用便捷函数获取配置:")
    app_config = get_app_config()
    browser_config = get_browser_config()
    logging_config = get_logging_config()
    
    print(f"   应用环境: {app_config.environment}")
    print(f"   调试模式: {app_config.debug}")
    print(f"   浏览器通道: {browser_config.channel}")
    print(f"   无头模式: {browser_config.headless}")
    print(f"   日志级别: {logging_config.level}")
    print()
    
    # 方法2: 使用配置工厂
    print("2. 使用配置工厂:")
    factory = ConfigFactory()
    plugin_config = factory.plugin
    database_config = factory.database
    
    print(f"   插件目录: {plugin_config.plugins_dir}")
    print(f"   启用的插件: {plugin_config.enabled_plugins}")
    print(f"   使用 MongoDB: {database_config.use_mongo}")
    print(f"   使用 Redis: {database_config.use_redis}")
    print()
    
    # 方法3: 通过 EverythingAsInterface 使用配置
    print("3. 通过主系统类使用配置:")
    system = EverythingAsInterface()
    
    print(f"   项目根目录: {system.app_config.project_root}")
    print(f"   账户存储路径: {system.app_config.accounts_path}")
    print(f"   数据存储路径: {system.app_config.data_path}")
    print(f"   浏览器视口: {system.browser_config.viewport.width}x{system.browser_config.viewport.height}")
    print(f"   浏览器超时: {system.browser_config.timeout_ms}ms")
    print()
    
    # 方法4: 从配置文件加载
    print("4. 从配置文件加载 (如果存在):")
    config_file = project_root / "config.json"
    if config_file.exists():
        system_with_file = EverythingAsInterface(config_file=str(config_file))
        print(f"   从文件加载的环境: {system_with_file.app_config.environment}")
    else:
        print("   配置文件不存在，使用默认配置")
    print()
    
    # 展示环境变量配置
    print("5. 环境变量配置示例:")
    print("   可以通过以下环境变量来配置系统:")
    print("   - ENVIRONMENT=production")
    print("   - DEBUG=true")
    print("   - BROWSER_CHANNEL=chrome")
    print("   - BROWSER_HEADLESS=true")
    print("   - LOG_LEVEL=DEBUG")
    print("   - APP_MASTER_KEY=your-secret-key")
    print()
    
    print("=== 配置系统演示完成 ===")


if __name__ == "__main__":
    demonstrate_config_usage()