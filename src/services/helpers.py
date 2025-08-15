from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Tuple, TypeVar

from playwright.async_api import Page

from src.services.base import ServiceConfig, ServiceDelegate, NetServiceDelegate
from src.services.xiaohongshu.collections.note_net_collection import (
    NoteNetCollectionState,
    record_response,
)
from src.utils.net_rule_bus import NetRuleBus, MergedEvent
from src.utils.net_rules import ResponseView
from src.utils.scrolling import (
    DefaultScrollStrategy,
    PagerClickStrategy,
    ScrollStrategy,
    SelectorScrollStrategy,
)


T = TypeVar("T")


@dataclass
class ScrollHelper:
    """Factory for building on_scroll coroutine based on config/extra."""

    @staticmethod
    def build_on_scroll(
        page: Page,
        *,
        service_config: ServiceConfig,
        pause_ms: int,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Callable[[], Awaitable[None]]:
        async def on_scroll() -> None:
            try:
                strat: ScrollStrategy
                # Prefer ServiceConfig if specified
                if service_config.scroll_mode == "selector" and service_config.scroll_selector:
                    strat = SelectorScrollStrategy(service_config.scroll_selector, pause_ms=pause_ms)
                elif service_config.scroll_mode == "pager" and service_config.pager_selector:
                    strat = PagerClickStrategy(service_config.pager_selector, wait_ms=pause_ms)
                else:
                    ex = (extra or {})
                    if ex.get("scroll_selector"):
                        strat = SelectorScrollStrategy(ex["scroll_selector"], pause_ms=pause_ms)
                    elif ex.get("pager_selector"):
                        strat = PagerClickStrategy(ex["pager_selector"], wait_ms=pause_ms)
                    else:
                        strat = DefaultScrollStrategy(pause_ms=pause_ms)
                await strat.scroll(page)
            except Exception:
                pass

        return on_scroll


PayloadValidator = Callable[[Any], bool]
DefaultParser = Callable[[Dict[str, Any]], Awaitable[List[T]]]


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
        state: NoteNetCollectionState[T],
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
        # unbind bus
        unbind = self._unbind
        self._unbind = None
        if unbind:
            try:
                unbind()
            except Exception:
                pass

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
        validator = payload_ok or (lambda d: isinstance(d, dict) and d.get("code") == 0)
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
                continue

            # Delegate can observe raw response first
            if self.delegate.on_response and self.state:
                try:
                    await self.delegate.on_response(evt.view, self.state)
                except Exception:
                    pass

            # Whether to record into state.raw_responses/last_response
            should_record = True
            if self.delegate.should_record_response:
                try:
                    should_record = bool(self.delegate.should_record_response(data, evt.view))
                except Exception:
                    should_record = True
            if should_record and self.state:
                try:
                    record_response(self.state, data, evt.view)
                except Exception:
                    pass

            # Let delegate parse items first; if returns None, fallback to default
            parsed: Optional[List[T]] = None
            if self.delegate.parse_items:
                try:
                    parsed = await self.delegate.parse_items(data)
                except Exception:
                    parsed = None

            if parsed is None:
                try:
                    payload = data.get("data", {}) if isinstance(data, dict) else data
                    parsed = await default_parse_items(payload)
                except Exception:
                    parsed = []

            # Post-process via delegate and append to state
            if parsed and self.state:
                try:
                    if self.delegate.on_items_collected:
                        parsed = await self.delegate.on_items_collected(parsed, self.state)
                except Exception:
                    pass
                try:
                    self.state.items.extend(parsed)
                except Exception:
                    pass
                if self.state.event:
                    try:
                        self.state.event.set()
                    except Exception:
                        pass


