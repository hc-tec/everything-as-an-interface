from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, TypeVar

from playwright.async_api import Page

from src.services.base_service import ServiceDelegate, BaseService
from src.services.collection_common import StopDecider
from src.services.collection_loop import CollectionLoopDelegate, OnLoopItemStart, OnLoopItemCollected, OnLoopItemEnd
from src.services.net_collection_loop import NetCollectionState
# from src.services.net_consume_helpers import NetConsumeHelper

from src.utils.net_rules import ResponseView

T = TypeVar("T")

ServiceDelegateOnBeforeResponse = Callable[[int, Dict[str, Any], Optional[NetCollectionState[T]]], Awaitable[None]]
ServiceDelegateOnResponse = Callable[[ResponseView, int, Dict[str, Any], Optional[NetCollectionState[T]]], Awaitable[None]]
ServiceDelegateShouldRecordResponse = Callable[[Any, ResponseView, int, Dict[str, Any], Optional[NetCollectionState[T]]], bool]
ServiceDelegateParseItems = Callable[[Dict[str, Any], int, Dict[str, Any], Optional[NetCollectionState[T]]], Awaitable[Optional[List[T]]]]
ServiceDelegateOnItemsCollected = Callable[[List[T], int, Dict[str, Any], Optional[NetCollectionState[T]]], Awaitable[List[T]]]

# 上面回调函数的参数格式见下方
# async def on_before_response(self, consume_count: int, extra: Dict[str, Any], state: Optional[NetCollectionState[T]]) -> None:  # pragma: no cover - default no-op
#     return None
#
# async def on_response(self, response: ResponseView, consume_count: int, extra: Dict[str, Any], state: Optional[NetCollectionState[T]]) -> None:  # pragma: no cover - default no-op
#     return None
#
# def should_record_response(self, payload: Any, response_view: ResponseView, consume_count: int, extra: Dict[str, Any], state: Optional[NetCollectionState[T]]) -> bool:  # pragma: no cover - default yes
#     return True
#
# async def parse_items(self, payload: Dict[str, Any], consume_count: int, extra: Dict[str, Any], state: Optional[NetCollectionState[T]]) -> Optional[List[T]]:  # pragma: no cover - default None
#     return None
#
# async def on_items_collected(self, items: List[T], consume_count: int, extra: Dict[str, Any], state: Optional[NetCollectionState[T]]) -> List[T]:  # pragma: no cover - default passthrough
#     return items

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


class NetService(BaseService, Generic[T]):

    def __init__(self):
        super().__init__()
        self.delegate = NetServiceDelegate()
        self.loop_delegate = CollectionLoopDelegate()
        self.page: Optional[Page] = None
        self.state: Optional[NetCollectionState[T]] = None
        self._net_helper: Optional[Any[T]] = None # NetConsumeHelper

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

    def set_delegate_on_loop_item_start(self, on_loop_item_start: OnLoopItemStart[T]) -> None:
        self.state.on_loop_item_start = on_loop_item_start

    def set_delegate_on_loop_item_collected(self, on_loop_item_collected: OnLoopItemCollected[T]) -> None:
        self.state.on_loop_item_collected = on_loop_item_collected

    def set_delegate_on_loop_item_end(self, on_loop_item_end: OnLoopItemEnd) -> None:
        self.state.on_loop_item_end = on_loop_item_end

    def _inject_raw_data(self, payload: Any):
        if self._service_params.need_raw_data:
            return payload
        return None

    def set_stop_decider(self, decider: Optional[StopDecider[T]]) -> None:  # pragma: no cover - interface
        if self.state:
            self.state.stop_decider = decider


