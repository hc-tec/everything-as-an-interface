"""
Everything As An Interface - 万物皆接口

将各种网站和应用转换为可编程接口，实现自动化和数据聚合
"""

import logging
from typing import Dict, Any

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("everything-as-an-interface.log")
    ]
)

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
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化万物皆接口系统
        
        Args:
            config: 系统配置
        """
        self.config = config or {}
        self.logger = logging.getLogger("everything_as_interface")
        
        # 初始化核心组件
        self.plugin_manager = PluginManager()
        self.scheduler = Scheduler()
        self.captcha_center = CaptchaCenter()
        self.subscription_system = SubscriptionSystem()
        self.notification_center = NotificationCenter()
        self.account_manager = AccountManager(
            master_key=self.config.get("master_key"),
            storage_path=self.config.get("accounts_path", "./accounts")
        )
        
        # 组件相互连接
        self.scheduler.set_plugin_manager(self.plugin_manager)
        self.scheduler.set_notification_center(self.notification_center)
        self.scheduler.set_account_manager(self.account_manager)
        
        self.logger.info("Everything As Interface 初始化完成")

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