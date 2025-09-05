import datetime
import json
from src.config import get_logger
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from settings import PROJECT_ROOT
from src.core.plugin_context import PluginContext
from src.core.task_params import TaskParams
from src.config.plugin_config import PluginConfig
from src.plugins.plugin_response import ResponseFactory
from src.utils import ValidationError
from src.utils.file_util import write_json_with_project_root
from src.utils.global_response_listener import add_global_response_listener
from src.utils.login_helper import create_login_helper
from src.utils.net_rules import ResponseView
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)


class BasePlugin:
    """
    插件基类：所有自动化接口插件都需继承此类
    
    插件生命周期：
    1. 初始化（__init__）
    2. 配置（set_params）
    3. 启动（start）
    4. 执行（fetch）
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

    PLUGIN_NEED_BROWSER: bool = True
    
    def __init__(self, plugin_config: Optional[PluginConfig] = None) -> None:
        self.task_params: Optional[TaskParams] = None
        self.plugin_config: Optional[PluginConfig] = plugin_config
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
        self._response = ResponseFactory(self.PLUGIN_ID, self.PLUGIN_VERSION)

    def inject_task_params(self, params: TaskParams) -> None:
        """
        配置插件
        
        Args:
            params: 任务参数
        """
        self.task_params = params
        logger.info(f"插件 {self.PLUGIN_ID} 参数已注入")
    
    def set_context(self, ctx: PluginContext) -> None:
        """
        注入外部上下文，内含 page、browser_context、account_manager 等。
        """
        self.ctx = ctx
        self.page = self.ctx.page
        self.account_manager = self.ctx.account_manager
        logger.info(f"插件 {self.PLUGIN_ID} 已注入 Context")
        
        # 仅在有 page 时创建登录助手
        if self.page is not None:
            self._login_helper = create_login_helper(
                page=self.page,
                account_manager=self.account_manager,
                task_config=self.task_params,
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
        else:
            logger.info(f"插件 {self.PLUGIN_ID} 运行在无浏览器模式，跳过登录助手创建")
            self._login_helper = None


    async def start(self) -> bool:
        """
        启动插件
        
        Returns:
            是否成功启动
        """
        valid = self.validate_params()
        if not valid["valid"]:
            logger.error("validation failed, error=%s", valid["errors"])
            raise ValidationError(valid["errors"])
        self.running = True
        logger.info(f"插件 {self.PLUGIN_ID} 已启动")
        return True
    
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

    def validate_params(self) -> Dict[str, Any]:
        """
        验证参数是否合法

        Returns:
            验证结果，包含是否成功和错误信息
        """
        errors = []
        
        # 检查插件是否启用
        if self.plugin_config and not self.plugin_config.is_plugin_enabled(self.PLUGIN_ID):
            errors.append(f"插件 {self.PLUGIN_ID} 未启用")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def get_plugin_settings(self) -> Dict[str, Any]:
        """
        获取插件设置
        
        Returns:
            插件设置字典
        """
        if self.plugin_config:
            return self.plugin_config.get_plugin_settings(self.PLUGIN_ID)
        return {}

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

    async def _dont_open_new_page(self):
        # 可选：走“强制单标签页”策略
        context = self.ctx.browser_context
        if not context:
            return
        await context.add_init_script("window.open = (url) => { location.href = url; return window; }")
        await context.add_init_script("document.addEventListener('click', e => { const a=e.target?.closest('a[target=_blank]'); if(a) a.target='_self'; }, true)")
        logger.info("已尝试让网页不再打开新页面，而是直接在原页面打开，这样可以防止（网络监听或元素选择）的page切换")
