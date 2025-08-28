
import asyncio
from src.config import get_logger
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright

from .plugin_context import PluginContext
from ..config.browser_config import BrowserConfig

logger = get_logger(__name__)

class Orchestrator:
    def __init__(
        self,
        browser_config: Optional[BrowserConfig] = None,
        *,
        # 保持向后兼容性的参数
        channel: Optional[str] = None,
        default_headless: Optional[bool] = None,
        default_viewport: Optional[Dict[str, int]] = None,
        default_user_agent: Optional[str] = None,
        proxy: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._playwright = None
        self._browser = None
        
        # 使用配置类或回退到传统参数
        if browser_config:
            self._browser_config = browser_config
        else:
            # 创建默认配置并应用传统参数
            self._browser_config = BrowserConfig()
            if channel is not None:
                self._browser_config.channel = channel
            if default_headless is not None:
                self._browser_config.headless = default_headless
            if default_viewport is not None:
                self._browser_config.viewport_width = default_viewport.get("width", 1280)
                self._browser_config.viewport_height = default_viewport.get("height", 800)
            if default_user_agent is not None:
                self._browser_config.user_agent = default_user_agent
            if proxy is not None:
                self._browser_config.proxy_server = proxy.get("server")
                self._browser_config.proxy_username = proxy.get("username")
                self._browser_config.proxy_password = proxy.get("password")

    async def start(
        self,
        *,
        headless: Optional[bool] = None,
        channel: Optional[str] = None,
        proxy: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        if self._browser is None:
            # 使用配置类生成启动选项
            launch_kwargs = self._browser_config.get_launch_options()
            
            # 允许运行时覆盖
            if headless is not None:
                launch_kwargs["headless"] = headless
            if channel is not None:
                launch_kwargs["channel"] = channel
            if proxy is not None:
                launch_kwargs["proxy"] = proxy
                
            self._browser = await self._playwright.chromium.launch(**launch_kwargs)

    async def stop(self) -> None:
        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
        except Exception as e:
            logger.warning(f"浏览器关闭失败: {str(e)}")
        finally:
            self._browser = None

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            logger.warning(f"playwright关闭失败: {str(e)}")
        finally:
            self._playwright = None

    async def allocate_context_page(
        self,
        *,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
        cookie_items: Optional[List[Dict[str, Any]]] = None,
        logger: Any = None,
        settings: Optional[Dict[str, Any]] = None,
        account_manager: Optional[Any] = None,
        extra_http_headers: Optional[Dict[str, str]] = None,
    ) -> PluginContext:
        if self._browser is None:
            raise RuntimeError("Orchestrator 未启动，请先调用 start()")
            
        # 使用配置类生成上下文选项
        context_args = self._browser_config.get_context_options()
        
        # 允许运行时覆盖
        if viewport is not None:
            context_args["viewport"] = viewport
        if user_agent is not None:
            context_args["user_agent"] = user_agent

        context = await self._browser.new_context(**context_args)
        if extra_http_headers:
            await context.set_extra_http_headers(extra_http_headers)
        if cookie_items:
            await context.add_cookies(cookie_items)
        page = await context.new_page()
        return PluginContext(
            page=page,
            browser_context=context,
            account_manager=account_manager,
            storage=None,
            event_bus=None,
            logger=logger or None,
            settings=settings or {},
        )

    async def release_context_page(self, ctx: PluginContext) -> None:
        try:
            await ctx.browser_context.close()
        except Exception:
            pass