import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.core.task_config import TaskConfig
from src.core.account_manager import AccountManager
from src.core.plugin_context import PluginContext
from src.utils.login_helper import create_login_helper

logger = logging.getLogger("base_plugin")

class BasePlugin(ABC):
    """
    插件基类：所有自动化接口插件都需继承此类
    
    插件生命周期：
    1. 初始化（__init__）
    2. 配置（configure）
    3. 启动（start）
    4. 执行/轮询（fetch/poll）
    5. 停止（stop）
    """
    
    # 每个插件必须定义唯一的插件ID
    PLUGIN_ID: str = ""
    # 插件名称
    PLUGIN_NAME: str = ""
    # 插件描述
    PLUGIN_DESCRIPTION: str = ""
    # 插件版本
    PLUGIN_VERSION: str = "0.1.0"
    # 插件作者
    PLUGIN_AUTHOR: str = ""
    
    def __init__(self):
        self.config: Optional[TaskConfig] = None
        self.running: bool = False
        self.accounts: List[Dict[str, Any]] = []
        self.selected_account: Optional[Dict[str, Any]] = None
        self._last_data: Any = None
        self.input_data: Dict[str, Any] = {}
        # 注入的 Playwright Page（或等价对象）
        self.page: Optional[Page] = None
        # 注入的运行上下文（可选）
        self.ctx: Optional[PluginContext] = None
        self.account_manager = None
        # 新增：延迟创建的登录助手
        self._login_helper = None
    
    def configure(self, config: TaskConfig) -> None:
        """
        配置插件
        
        Args:
            config: 插件配置
        """
        self.config = config
        logger.info(f"插件 {self.PLUGIN_ID} 已配置")
    
    def set_context(self, ctx: PluginContext) -> None:
        """
        注入外部上下文，内含 page、browser_context、account_manager 等。
        """
        self.ctx = ctx
        self.page = self.ctx.page
        self.account_manager = self.ctx.account_manager
        logger.info(f"插件 {self.PLUGIN_ID} 已注入 Context")
        # 创建登录助手（在有上下文后）
        self._login_helper = create_login_helper(
            page=self.page,
            account_manager=self.account_manager,
            task_config=self.config,
            plugin_attrs={
                # 透传可能存在的类属性，便于向后兼容
                "LOGIN_URL": getattr(self, "LOGIN_URL", None),
                "PROBE_URL": getattr(self, "PROBE_URL", None),
                "HOME_URL": getattr(self, "HOME_URL", None),
                "PLATFORM_ID": getattr(self, "PLATFORM_ID", None),
                "LOGGED_IN_SELECTORS": getattr(self, "LOGGED_IN_SELECTORS", None),
                "COOKIE_DOMAINS": getattr(self, "COOKIE_DOMAINS", None),
            }
        )


    @abstractmethod
    async def start(self) -> bool:
        """
        启动插件
        
        Returns:
            是否成功启动
        """
        valid = self.validate_config()
        if not valid["valid"]:
            logger.error("validation failed, error=%s", valid["error"])
            return valid["valid"]
        self.running = True
        logger.info(f"插件 {self.PLUGIN_ID} 已启动")
        return True
    
    @abstractmethod
    async def stop(self) -> bool:
        """
        停止插件
        
        Returns:
            是否成功停止
        """
        self.running = False
        logger.info(f"插件 {self.PLUGIN_ID} 已停止")
        return True
    
    @abstractmethod
    async def fetch(self) -> Dict[str, Any]:
        """
        获取数据
        
        Returns:
            获取到的数据
        """
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        获取插件元数据
        
        Returns:
            插件元数据
        """
        return {
            "id": self.PLUGIN_ID,
            "name": self.PLUGIN_NAME,
            "description": self.PLUGIN_DESCRIPTION,
            "version": self.PLUGIN_VERSION,
            "author": self.PLUGIN_AUTHOR,
        }
    
    def handle_captcha(self, captcha_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理验证码
        
        Args:
            captcha_data: 验证码数据
            
        Returns:
            处理结果
        """
        # 默认实现，子类可覆盖
        return {"success": False, "message": "未实现验证码处理"}

    def validate_config(self) -> Dict[str, Any]:
        """
        验证配置是否合法

        Returns:
            验证结果，包含是否成功和错误信息
        """
        # 默认实现，子类应当覆盖
        return {"valid": True, "errors": []}

    def _get_auth_config(self) -> Dict[str, Any]:
        """
        兼容旧接口：从任务与插件属性构建认证配置。
        注意：具体登录流程已迁移到 login_helper。
        """
        # 复用 login_helper 的解析结果，避免重复逻辑
        if not self._login_helper:
            return {}
        return self._login_helper.auth_config.get_config()

    async def _try_cookie_login(self) -> bool:
        """兼容旧接口：委托给 login_helper 实现。"""
        if not self._login_helper:
            return False
        # BasePlugin 层不做站点判断，站点专属检查仍由子类 _is_logged_in 覆盖。
        # 这里将 selectors 传 None，login_helper 会从配置读取。
        return await self._login_helper.try_cookie_login()

    async def _manual_login(self, login_url: Optional[str] = None) -> bool:
        """兼容旧接口：委托给 login_helper 实现。"""
        if not self._login_helper:
            return False
        return await self._login_helper.manual_login(login_url=login_url)

    async def _ensure_logged_in(self) -> bool:
        """
        确保登录状态：优先 Cookie 登录；失败则引导手动登录。
        """
        if not self._login_helper:
            return False
        return await self._login_helper.ensure_logged_in()

    async def _is_logged_in(self) -> bool:
        """
        通用的登录检测：默认委托给 login_helper，子类可覆盖为站点专属逻辑。
        """
        if not self._login_helper:
            return False
        # 允许通过类属性 LOGGED_IN_SELECTORS 传递默认选择器
        selectors = getattr(self, "LOGGED_IN_SELECTORS", None)
        return await self._login_helper.is_logged_in(selectors=selectors)
