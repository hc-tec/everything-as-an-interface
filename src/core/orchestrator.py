import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright

from .plugin_context import PluginContext

class Orchestrator:
    def __init__(
        self,
        *,
        channel: str = "msedge",
        default_headless: bool = False,
        default_viewport: Dict[str, int] = {"width": 1280, "height": 800},
        default_user_agent: Optional[str] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/96.0.4664.110 Safari/537.36"
        ),
        proxy: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._playwright = None
        self._browser = None
        self._channel = channel
        self._default_headless = default_headless
        self._default_viewport = default_viewport
        self._default_user_agent = default_user_agent
        self._proxy = proxy  # e.g., {"server": "http://host:port", "username": "...", "password": "..."}

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
            launch_kwargs: Dict[str, Any] = {
                "headless": self._default_headless if headless is None else headless,
                "channel": channel or self._channel,
            }
            use_proxy = proxy if proxy is not None else self._proxy
            if use_proxy:
                launch_kwargs["proxy"] = use_proxy
            self._browser = await self._playwright.chromium.launch(**launch_kwargs)

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
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
        context_args: Dict[str, Any] = {
            "viewport": viewport or self._default_viewport,
        }
        ua = user_agent or self._default_user_agent
        if ua:
            context_args["user_agent"] = ua
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