from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Tuple, TypeVar

from playwright.async_api import Page

from src.services.net_service import NetServiceDelegate
from src.services.net_collection_loop import (
    NetCollectionState,
    record_response,
)
from src.utils.net_rule_bus import NetRuleBus, MergedEvent
from src.utils.net_rules import ResponseView
# 导入统一的日志配置
from src.config import get_logger
T = TypeVar("T")

logger = get_logger(__name__)

PayloadValidator = Callable[[Any], bool]
DefaultParser = Callable[[Dict[str, Any], int, Dict[str, Any], Optional[NetCollectionState[T]]], Awaitable[List[T]]]


class NetConsumeHelper(Generic[T]):
    """Generic network consumer glue for services.

    Responsibilities:
      - Bind NetRuleBus and subscribe patterns
      - Consume merged queue, validate payload, delegate hooks
      - Record raw responses into state and parse items (delegate or default)
      - Append parsed items to state and signal event
    """

    def __init__(
        self,
        *,
        state: NetCollectionState[T],
        delegate: NetServiceDelegate[T] = None,
    ) -> None:
        self.state = state
        self.delegate = delegate
        self._bus: Optional[NetRuleBus] = None
        self._unbind: Optional[Callable[[], None]] = None
        self._merged_q: Optional[asyncio.Queue] = None
        self._subs_meta: Dict[int, Tuple[str, str]] = {}
        self._consumer: Optional[asyncio.Task] = None
        self._extra: Optional[Dict[str, Any]] = None
        self._consume_count: int = 0

    async def bind(self, page: Page, subscribe_patterns: List[Tuple[str, str]]) -> None:
        self._bus = NetRuleBus()
        self._unbind = await self._bus.bind(page)
        self._merged_q, self._subs_meta = self._bus.subscribe_many(subscribe_patterns)

    async def start(
        self,
        *,
        default_parse_items: DefaultParser[T],
        payload_ok: Optional[PayloadValidator] = None,
    ) -> None:
        if self._consumer:
            return
        self._consumer = asyncio.create_task(
            self._consume_loop(default_parse_items=default_parse_items, payload_ok=payload_ok)
        )

    async def stop(self) -> None:
        # stop consumer
        if self._consumer:
            try:
                self._consumer.cancel()
                with asyncio.CancelledError:  # type: ignore[attr-defined]
                    pass
            except Exception:
                pass
            try:
                with asyncio.CancelledError:
                    await self._consumer
            except Exception:
                pass
            self._consumer = None
        # unsubscribe to cleanup forward tasks
        if self._bus and self._subs_meta:
            try:
                self._bus.unsubscribe_many_by_ids(list(self._subs_meta.keys()))
            except Exception:
                pass
            self._subs_meta = {}
        # unbind bus
        unbind = self._unbind
        self._unbind = None
        if unbind:
            try:
                unbind()
            except Exception:
                pass
        self._bus = None

    def set_extra(self, extra: Dict[str, Any]) -> None:
        self._extra = extra

    async def _consume_loop(
        self,
        *,
        default_parse_items: DefaultParser[T],
        payload_ok: Optional[PayloadValidator] = None,
    ) -> None:
        if not self._merged_q:
            return
        validator = payload_ok or (lambda x: True)
        while True:
            self._consume_count += 1
            if self.delegate.on_before_response:
                await self.delegate.on_before_response(self._consume_count, self._extra, self.state)
            try:
                evt: MergedEvent = await self._merged_q.get()
            except asyncio.CancelledError:
                break
            except Exception:
                continue

            if not isinstance(evt.view, ResponseView):
                continue

            try:
                data = evt.view.data()
            except Exception:
                data = None

            if not validator(data):
                logger.info("Received invalid data: %s", data)
                continue

            # Delegate can observe raw response first
            if self.delegate.on_response and self.state:
                try:
                    await self.delegate.on_response(evt.view, self._consume_count, self._extra, self.state)
                except Exception:
                    logger.error("on_response error", exc_info=True)

            # Whether to record into state.raw_responses/last_response
            should_record = True
            if self.delegate.should_record_response:
                try:
                    should_record = bool(self.delegate.should_record_response(data, evt.view, self._consume_count, self._extra, self.state))
                except Exception:
                    should_record = True
            if should_record and self.state:
                try:
                    record_response(self.state, data, evt.view, self._consume_count, self._extra)
                except Exception:
                    logger.error("record_response error", exc_info=True)

            # Let delegate parse items first; if returns None, fallback to default
            parsed: Optional[List[T]] = None
            if self.delegate.parse_items:
                try:
                    parsed = await self.delegate.parse_items(data, self._consume_count, self._extra, self.state)
                except Exception:
                    parsed = None
                    logger.error("parse_items error", exc_info=True)

            if parsed is None:
                try:
                    payload = data
                    parsed = await default_parse_items(payload, self._consume_count, self._extra, self.state)
                except Exception:
                    parsed = []
                    logger.error("default_parse_items error", exc_info=True)

            # Post-process via delegate and append to state
            if self.state:
                try:
                    if self.delegate.on_items_collected:
                        parsed = await self.delegate.on_items_collected(parsed, self._consume_count, self._extra, self.state)
                except Exception:
                    logger.error("on_items_collected error", exc_info=True)
                try:
                    self.state.items.extend(parsed)
                except Exception:
                    pass
                if self.state.queue:
                    try:
                        await self.state.queue.put(parsed)
                    except Exception:
                        pass


