from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, TypeVar

from playwright.async_api import Page

from src.services.net_collection import NetCollectionState
from src.utils.net_rules import ResponseView

T = TypeVar("T")

# StopDecider = Callable[[Page, List[Any], Optional[Any], List[T], List[T], float, Dict[str, Any], Optional[ResponseView]], bool | Awaitable[bool]]

ServiceDelegateOnAttach = Callable[[Page], Awaitable[None]]
ServiceDelegateOnDetach = Callable[[], Awaitable[None]]
ServiceDelegateOnBeforeResponse = Callable[[int, Dict[str, Any], Optional[NetCollectionState[T]]], Awaitable[None]]
ServiceDelegateOnResponse = Callable[[ResponseView, Optional[NetCollectionState[T]]], Awaitable[None]]
ServiceDelegateShouldRecordResponse = Callable[[Any, ResponseView], bool]
ServiceDelegateParseItems = Callable[[Dict[str, Any]], Awaitable[Optional[List[T]]]]
ServiceDelegateOnItemsCollected = Callable[[List[T], Optional[NetCollectionState[T]]], Awaitable[List[T]]]

# 上面回调函数的参数格式见下方
# async def on_attach(self, page: Page) -> None:  # pragma: no cover - default no-op
#     return None
#
# async def on_detach(self) -> None:  # pragma: no cover - default no-op
#     return None
#
# async def on_before_response(self, consume_count: int, extra: Dict[str, Any], state: Optional[NetCollectionState[T]]) -> None:  # pragma: no cover - default no-op
#     return None
#
# async def on_response(self, response: ResponseView, state: Optional[NetCollectionState[T]]) -> None:  # pragma: no cover - default no-op
#     return None
#
# def should_record_response(self, payload: Any, response_view: ResponseView) -> bool:  # pragma: no cover - default yes
#     return True
#
# async def parse_items(self, payload: Dict[str, Any]) -> Optional[List[T]]:  # pragma: no cover - default None
#     return None
#
# async def on_items_collected(self, items: List[T], state: Optional[NetCollectionState[T]]) -> List[T]:  # pragma: no cover - default passthrough
#     return items


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
        concurrency: Desired concurrency for request generation (advisory).
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
    concurrency: int = 1
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
        self._unbind: Optional[Callable[[], None]] = None
        self._service_config: ServiceConfig = ServiceConfig()
        self.delegate = ServiceDelegate()

    def set_delegate(self, delegate: ServiceDelegate) -> None:
        self.delegate = delegate

    async def attach(self, page: Page) -> None:
        """Attach the service onto a Page (bind network rules, init state)."""
        raise NotImplementedError()

    async def detach(self) -> None:
        unbind = self._unbind
        self._unbind = None
        if unbind:
            try:
                unbind()
            except Exception:
                pass

    def configure(self, cfg: ServiceConfig) -> None:  # pragma: no cover - simple setter
        self._service_config = cfg

    def set_delegate_on_attach(self, on_attach: ServiceDelegateOnAttach) -> None:
        self.delegate.on_attach = on_attach

    def set_delegate_on_detach(self, on_detach: ServiceDelegateOnDetach) -> None:
        self.delegate.on_detach = on_detach


# Unified delegate interface
class NetServiceDelegate(ServiceDelegate, Generic[T]):
    """Unified delegate for all services.

    Hooks are optional; default implementations are no-ops to preserve built-in behavior.
    """
    on_before_response: Optional[ServiceDelegateOnBeforeResponse[T]] = None
    on_response: Optional[ServiceDelegateOnResponse[T]] = None
    should_record_response: Optional[ServiceDelegateShouldRecordResponse] = None
    parse_items: Optional[ServiceDelegateParseItems[T]] = None
    on_items_collected: Optional[ServiceDelegateOnItemsCollected[T]] = None

class NetService(BaseSiteService, Generic[T]):

    def __init__(self):
        super().__init__()
        self.delegate = NetServiceDelegate()
        self.page: Optional[Page] = None

    def set_delegate_on_before_response(self, on_before_response: ServiceDelegateOnBeforeResponse[T]) -> None:
        self.delegate.on_before_response = on_before_response

    def set_delegate_on_response(self, on_response: ServiceDelegateOnResponse[T]) -> None:
        self.delegate.on_response = on_response

    def set_delegate_should_record_response(self, should_record_response: ServiceDelegateShouldRecordResponse) -> None:
        self.delegate.should_record_response = should_record_response

    def set_delegate_parse_items(self, parse_items: ServiceDelegateParseItems[T]) -> None:
        self.delegate.parse_items = parse_items

    def set_delegate_on_items_collected(self, on_items_collected: ServiceDelegateOnItemsCollected[T]) -> None:
        self.delegate.on_items_collected = on_items_collected
