"""
Everything As An Interface - 万物皆接口

将各种网站和应用转换为可编程接口，实现自动化和数据聚合
"""

from typing import Dict, Any, Optional

# 导入配置管理
from .config.config_factory import ConfigFactory
from .config.app_config import AppConfig
from .config.logging_config import LoggingConfig

# 导入统一的日志配置
from .config import setup_logging, get_logger

# 导入核心组件
from .core.plugin_manager import PluginManager
from .core.scheduler import Scheduler
from .core.captcha_center import CaptchaCenter
from .core.subscription import SubscriptionSystem
from .core.notification import NotificationCenter
from .core.account_manager import AccountManager

# 导入工具类
from .utils.browser import BrowserAutomation

# 导入插件基类
from .plugins.base import BasePlugin

# 版本信息
__version__ = "0.1.0"

class EverythingAsInterface:
    """万物皆接口核心类"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化万物皆接口系统
        
        Args:
            config_file: 配置文件路径
        """
        # 初始化配置工厂
        self.config_factory = ConfigFactory()
        
        # 加载配置
        if config_file:
            configs = self.config_factory.load_from_file(config_file)
        else:
            configs = self.config_factory.create_all_configs()
        
        # 提取各个配置对象
        self.app_config = configs["app"]
        self.browser_config = configs["browser"]
        self.database_config = configs["database"]
        self.logging_config = configs["logging"]
        self.plugin_config = configs["plugin"]
        self.webhook_config = configs["webhook"]
        
        # 验证配置
        self.config_factory.validate_params(self.app_config)
        self.config_factory.validate_params(self.browser_config)
        
        # 设置日志
        setup_logging(
            logging_config=self.logging_config
        )
        
        self.logger = get_logger("everything_as_interface")
        
        # 初始化核心组件
        self.plugin_manager = PluginManager(plugin_config=self.plugin_config)
        self.scheduler = Scheduler()
        self.captcha_center = CaptchaCenter()
        self.subscription_system = SubscriptionSystem()
        self.notification_center = NotificationCenter()
        self.account_manager = AccountManager(
            master_key=self.app_config.master_key,
            storage_path=self.app_config.accounts_path
        )
        
        # 组件相互连接
        self.scheduler.set_plugin_manager(self.plugin_manager)
        self.scheduler.set_notification_center(self.notification_center)
        self.scheduler.set_account_manager(self.account_manager)
        
        self.logger.info(f"Everything As Interface 初始化完成 - 环境: {self.app_config.environment}")

# 导出主要类和组件
__all__ = [
    "EverythingAsInterface",
    "PluginManager",
    "Scheduler",
    "CaptchaCenter",
    "SubscriptionSystem",
    "NotificationCenter",
    "AccountManager",
    "BrowserAutomation",
    "BasePlugin",
]