from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, TypeVar, Dict, Any

from playwright.async_api import Page

T = TypeVar("T")

# StopDecider = Callable[[Page, List[Any], Optional[Any], List[T], List[T], float, Dict[str, Any], Optional[ResponseView]], bool | Awaitable[bool]]

ServiceDelegateOnAttach = Callable[[Page], Awaitable[None]]
ServiceDelegateOnDetach = Callable[[], Awaitable[None]]


# 上面回调函数的参数格式见下方
# async def on_attach(self, page: Page) -> None:  # pragma: no cover - default no-op
#     return None
#
# async def on_detach(self) -> None:  # pragma: no cover - default no-op
#     return None
#


# Unified delegate interface
class ServiceDelegate:
    """Unified delegate for all services.

    Hooks are optional; default implementations are no-ops to preserve built-in behavior.
    """
    on_attach: Optional[ServiceDelegateOnAttach] = None
    on_detach: Optional[ServiceDelegateOnDetach] = None

@dataclass
class ServiceConfig:
    """Common configuration for site services.

    Attributes:
        response_timeout_sec: Max seconds to wait for a response event.
        delay_ms: Delay between pages/batches/polls (when applicable).
        queue_maxsize: Optional queue size hint for internal buffers.
        max_pages: Optional page limit for paginated collectors.
        scroll_pause_ms: Pause after each scroll, in milliseconds.
        max_idle_rounds: Stop after this many consecutive idle rounds (for DOM collectors or custom loops).
        max_items: Optional item limit (applies where relevant).
        scroll_mode: Optional strategy indicator: "default" | "selector" | "pager".
        scroll_selector: Used when scroll_mode == "selector".
        pager_selector: Used when scroll_mode == "pager".
    """

    response_timeout_sec: float = 5.0
    delay_ms: int = 500
    queue_maxsize: Optional[int] = None
    scroll_pause_ms: int = 800
    max_idle_rounds: int = 2
    max_items: Optional[int] = None
    max_seconds: int = 600
    auto_scroll: bool = True
    scroll_mode: Optional[str] = None
    scroll_selector: Optional[str] = None
    max_pages: Optional[int] = None
    pager_selector: Optional[str] = None



class BaseSiteService:
    """Base for all site services (note/detail/publish etc.)."""

    def __init__(self) -> None:
        self._service_config: ServiceConfig = ServiceConfig()
        self.delegate = ServiceDelegate()

    def set_delegate(self, delegate: ServiceDelegate) -> None:
        self.delegate = delegate

    async def attach(self, page: Page) -> None:
        # Delegate hook
        if self.delegate.on_attach:
            try:
                await self.delegate.on_attach(page)
            except Exception:
                pass

    async def detach(self) -> None:
        # Delegate hook (before unbind)
        if self.delegate.on_detach:
            try:
                await self.delegate.on_detach()
            except Exception:
                pass

    def configure(self, extra: Dict[str, Any]) -> None:  # pragma: no cover - simple setter
        self._service_config = ServiceConfig(
            max_items=extra.get("max_items", ServiceConfig.max_items),
            max_seconds=extra.get("max_seconds", ServiceConfig.max_seconds),
            max_idle_rounds=extra.get("max_idle_rounds", ServiceConfig.max_idle_rounds),
            auto_scroll=extra.get("auto_scroll", ServiceConfig.auto_scroll),
            scroll_pause_ms=extra.get("scroll_pause_ms", ServiceConfig.scroll_pause_ms),
            scroll_mode=extra.get("scroll_mode", ServiceConfig.scroll_mode),
            scroll_selector=extra.get("scroll_selector", ServiceConfig.scroll_selector),
            max_pages=extra.get("max_pages", ServiceConfig.max_pages),
            pager_selector=extra.get("pager_selector", ServiceConfig.pager_selector),
        )

    def set_delegate_on_attach(self, on_attach: ServiceDelegateOnAttach) -> None:
        self.delegate.on_attach = on_attach

    def set_delegate_on_detach(self, on_detach: ServiceDelegateOnDetach) -> None:
        self.delegate.on_detach = on_detach


