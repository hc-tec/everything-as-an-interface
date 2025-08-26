"""
通用登录助手模块

提供平台无关的登录认证功能，支持多种认证方式和配置来源。
"""

import asyncio
from src.config import get_logger
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from playwright.async_api import Page
from src.core.account_manager import AccountManager
from src.core.task_params import TaskParams
from src.utils import wait_until_result

logger = get_logger(__name__)


class AuthConfig:
    """认证配置类，负责多层次配置的读取和解析"""
    
    def __init__(self, 
                 task_config: Optional[TaskParams] = None,
                 plugin_attrs: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化认证配置
        
        Args:
            task_config: 任务配置对象
            plugin_attrs: 插件类属性字典（用于向后兼容）
        """
        self.task_config = task_config
        self.plugin_attrs = plugin_attrs or {}
        self._config_cache: Optional[Dict[str, Any]] = None
    
    def get_config(self) -> Dict[str, Any]:
        """
        获取认证配置，支持多层次配置继承：
        1. 任务级配置 (task.extra.auth) - 最高优先级
        2. 插件类属性 (LOGIN_URL等) - 向后兼容
        3. 自动域名检测 - 兜底方案
        
        返回的配置包含：
        - login_url: 手动登录页面URL
        - probe_url/home_url: 用于检测登录状态的页面
        - platform_id: Cookie存储的平台标识（可选，支持自动检测）
        - logged_in_selectors: 登录状态检测的CSS选择器（可选）
        - cookie_domains: Cookie过滤的域名列表（可选，支持自动检测）
        """
        if self._config_cache is not None:
            return self._config_cache
        
        auth: Dict[str, Any] = {}
        
        # 1. 从任务配置读取（最高优先级）
        if self.task_config and self.task_config.extra:
            task_auth = self.task_config.extra.get("auth", {})
            if isinstance(task_auth, dict):
                auth.update(task_auth)
        
        # 2. 从插件类属性获取兜底配置（向后兼容）
        fallback_mapping = {
            "login_url": "LOGIN_URL",
            "probe_url": "PROBE_URL", 
            "home_url": "HOME_URL",
            "platform_id": "PLATFORM_ID",
            "logged_in_selectors": "LOGGED_IN_SELECTORS",
            "cookie_domains": "COOKIE_DOMAINS"
        }
        
        for config_key, attr_name in fallback_mapping.items():
            if config_key not in auth:
                value = self.plugin_attrs.get(attr_name)
                if value:
                    auth[config_key] = value
        
        # 3. 自动域名检测（最低优先级兜底）
        if not auth.get("platform_id") and auth.get("login_url"):
            try:
                parsed = urlparse(auth["login_url"])
                domain = parsed.netloc
                # 提取主域名作为平台标识（如 xiaohongshu.com）
                parts = domain.split(".")
                if len(parts) >= 2:
                    auth.setdefault("platform_id", ".".join(parts[-2:]))
                    auth.setdefault("cookie_domains", [domain, f".{'.'.join(parts[-2:])}"])
                else:
                    auth.setdefault("platform_id", domain)
                    auth.setdefault("cookie_domains", [domain])
            except Exception as e:
                logger.debug(f"自动域名检测失败: {e}")
        
        self._config_cache = auth
        return auth


class LoginHelper:
    """通用登录助手，提供平台无关的登录功能"""
    
    def __init__(self, 
                 page: Page,
                 account_manager: Optional[AccountManager] = None,
                 auth_config: Optional[AuthConfig] = None) -> None:
        """
        初始化登录助手
        
        Args:
            page: Playwright页面对象
            account_manager: 账号管理器（可选）
            auth_config: 认证配置对象（可选）
        """
        self.page = page
        self.account_manager = account_manager
        self.auth_config = auth_config or AuthConfig()
    
    async def is_logged_in(self, selectors: Optional[List[str]] = None) -> bool:
        """
        检测是否已登录
        
        Args:
            selectors: 登录状态检测选择器，优先于配置中的选择器
            
        Returns:
            是否已登录
        """
        try:
            if not self.page:
                return False
            
            # 确定检测选择器
            check_selectors = selectors
            if not check_selectors:
                config = self.auth_config.get_config()
                check_selectors = config.get("logged_in_selectors")
            
            if not check_selectors:
                logger.debug("未提供登录状态检测选择器，默认返回False")
                return False
            
            # 检测任一选择器是否存在
            for selector in check_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=2000)
                    if element:
                        logger.debug(f"检测到登录状态指示器: {selector}")
                        return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.debug(f"登录状态检测异常: {e}")
            return False
    
    async def try_cookie_login(self, 
                              probe_url: Optional[str] = None,
                              logged_in_selectors: Optional[List[str]] = None) -> bool:
        """
        尝试Cookie登录验证
        
        Args:
            probe_url: 探测页面URL，优先于配置中的URL
            logged_in_selectors: 登录状态检测选择器，优先于配置中的选择器
            
        Returns:
            是否登录成功
        """
        if not self.page:
            return False
        
        try:
            # 首先检查当前登录状态
            if await self.is_logged_in(logged_in_selectors):
                logger.debug("当前已处于登录状态")
                return True
            
            # 获取配置
            config = self.auth_config.get_config()
            
            # 确定探测URL
            test_url = probe_url or config.get("probe_url") or config.get("home_url") or config.get("login_url")
            
            if test_url:
                try:
                    logger.debug(f"访问探测页面触发Cookie识别: {test_url}")
                    # 访问探测页面
                    await self.page.goto(test_url, wait_until="domcontentloaded")
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.debug(f"访问探测页面失败: {e}")
            
            # 再次检查登录状态
            return await self.is_logged_in(logged_in_selectors)
            
        except Exception as exc:
            logger.warning(f"Cookie登录验证异常: {exc}")
            return False
    
    async def manual_login(self, 
                          login_url: Optional[str] = None,
                          logged_in_selectors: Optional[List[str]] = None,
                          timeout: int = 120000) -> bool:
        """
        手动登录流程
        
        Args:
            login_url: 登录页面URL，优先于配置中的URL
            logged_in_selectors: 登录状态检测选择器，优先于配置中的选择器
            timeout: 等待登录完成的超时时间（毫秒）
            
        Returns:
            是否登录成功
        """
        if not self.page:
            return False
        
        # 获取配置
        config = self.auth_config.get_config()
        
        # 确定登录URL
        url = login_url or config.get("login_url")
        if not url:
            logger.error("无法执行手动登录：未提供登录URL")
            logger.info("请提供登录URL：")
            logger.info("1. 方法参数: login_url")
            logger.info("2. 任务配置: extra.auth.login_url")
            logger.info("3. 插件类属性: LOGIN_URL")
            return False
        
        try:
            # 跳转到登录页
            await self.page.goto(url, wait_until="domcontentloaded")
            logger.info(f"已打开登录页面: {url}")
            logger.info("请手动完成登录，登录成功后Cookie将自动保存...")
            
            # 等待登录成功
            async def check_login():
                if await self.is_logged_in(logged_in_selectors):
                    logger.info("检测到登录成功，正在保存Cookie...")
                    
                    # 保存Cookie
                    await self._save_cookies_after_login(config, url)
                    return True
                return None
            
            # 等待登录完成
            result = await wait_until_result(check_login, timeout=timeout)
            return bool(result)
            
        except Exception as exc:
            logger.error(f"手动登录过程异常: {exc}")
            return False
    
    async def ensure_logged_in(self, 
                              login_url: Optional[str] = None,
                              probe_url: Optional[str] = None,
                              logged_in_selectors: Optional[List[str]] = None) -> bool:
        """
        确保登录状态（优先Cookie登录，失败则手动登录）
        
        Args:
            login_url: 登录页面URL
            probe_url: 探测页面URL
            logged_in_selectors: 登录状态检测选择器
            
        Returns:
            是否成功登录
        """
        if not self.page:
            return False
        
        # 1) 优先尝试Cookie登录
        if await self.try_cookie_login(probe_url, logged_in_selectors):
            return True
        
        # 2) 回退手动登录
        logger.info("Cookie登录失败，需要手动登录...")
        return await self.manual_login(login_url, logged_in_selectors)
    
    async def _save_cookies_after_login(self, config: Dict[str, Any], login_url: str):
        """登录成功后保存Cookie"""
        try:
            cookies = await self.page.context.cookies()
            if not cookies:
                logger.warning("未获取到Cookie")
                return
            
            # 确定平台标识和Cookie域名
            platform_id = config.get("platform_id")
            cookie_domains = config.get("cookie_domains")
            
            if not platform_id:
                # 从当前URL推断平台标识
                try:
                    current_url = self.page.url
                    parsed = urlparse(current_url)
                    domain = parsed.netloc
                    parts = domain.split(".")
                    platform_id = ".".join(parts[-2:]) if len(parts) >= 2 else domain
                    cookie_domains = [domain, f".{platform_id}"]
                except Exception:
                    platform_id = "unknown"
                    cookie_domains = []
            
            # 保存Cookie到账号管理器
            if self.account_manager and platform_id:
                # 确保平台存在（动态创建）
                if not self.account_manager.get_platform(platform_id):
                    self.account_manager.add_platform(
                        platform_id=platform_id,
                        name=platform_id.title(),
                        cookie_domains=cookie_domains or [platform_id],
                        login_url=login_url,
                        requires_login=True
                    )
                
                cookie_id = self.account_manager.add_cookies(
                    platform_id=platform_id, 
                    cookies=cookies, 
                    name=f"{platform_id}手动登录"
                )
                if cookie_id:
                    logger.info(f"Cookie已保存: {cookie_id} (平台: {platform_id})")
                else:
                    logger.warning("Cookie保存失败")
            else:
                logger.info("跳过Cookie持久化（无account_manager或platform_id）")
                
        except Exception as exc:
            logger.warning(f"保存Cookie时出错: {exc}")


def create_login_helper(page: Page,
                       account_manager: Optional[AccountManager] = None,
                       task_config: Optional[TaskParams] = None,
                       plugin_attrs: Optional[Dict[str, Any]] = None) -> LoginHelper:
    """
    创建登录助手实例的工厂函数
    
    Args:
        page: Playwright页面对象
        account_manager: 账号管理器
        task_config: 任务配置
        plugin_attrs: 插件类属性字典
        
    Returns:
        LoginHelper实例
    """
    auth_config = AuthConfig(task_config, plugin_attrs)
    return LoginHelper(page, account_manager, auth_config)