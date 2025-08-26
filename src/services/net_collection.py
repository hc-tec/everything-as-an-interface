from __future__ import annotations

import asyncio
from src.config import get_logger
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, TypeVar

from playwright.async_api import Page

from src.utils.net_rules import ResponseView
from src.services.collection_common import scroll_page_once as _scroll_page_once, NetStopDecider
from src.services.collection_loop import run_generic_collection

logger = get_logger(__name__)

T = TypeVar("T")

class NetCollectionState(Generic[T]):
    """Mutable state for a note net collection session."""

    page: Page
    queue: asyncio.Queue
    items: List[T] = []
    raw_responses: List[Any] = []
    last_raw_response: Optional[Any] = None
    last_response_view: Optional[ResponseView] = None
    stop_decider: Optional[NetStopDecider[T]] = None

    def __init__(self, page: Page, queue: asyncio.Queue, items=None,
                 raw_responses=None, last_raw_response: Optional[Any] = None,
                 last_response_view: Optional[ResponseView] = None, stop_decider: Optional[NetStopDecider[T]] = None):
        if raw_responses is None:
            raw_responses = []
        if items is None:
            items = []
        self.page = page
        self.queue = queue
        self.items = items
        self.raw_responses = raw_responses
        self.last_raw_response = last_raw_response
        self.last_response_view = last_response_view
        self.stop_decider = stop_decider

    def clear(self):
        self.items = []
        self.raw_responses = []
        self.last_raw_response = None
        self.last_response_view = None


def record_response(
        state: NetCollectionState[Any],
        data: Any,
        response_view: Optional[ResponseView],
        consume_count: int,
        extra: Dict[str, Any]) -> None:
    """Record a raw response and wake the collector loop."""
    try:
        state.raw_responses.append(data)
    except Exception:
        pass
    state.last_raw_response = data
    state.last_response_view = response_view

async def run_network_collection(
    state: NetCollectionState[T],
    cfg: "ServiceParams",
    *,
    extra_params: Optional[Dict[str, Any]] = None,
    goto_first: Optional[Callable[[], Awaitable[None]]] = None,
    on_scroll: Optional[Callable[[], Awaitable[None]]] = None,
    on_tick_start: Optional[Callable[[int, Dict[str, Any]], Awaitable[None]]] = None,
    key_fn: Optional[Callable[[T], Optional[str]]] = None,
    network_timeout: float = 5.0,
) -> List[T]:
    """Run a unified network-driven collection loop using the generic engine.

    This function assumes external code populates state.items and state.queue is
    set when new items arrive (e.g., via NetRuleBus consumer). It converts that
    contract into a generic on_tick callback that waits for the event.
    """

    async def on_tick() -> Optional[int]:
        # Wait for event with a short timeout to allow idle detection
        try:
            await state.queue.get()
        except asyncio.TimeoutError:
            logger.debug("network collection timed out")
            return 0
        finally:
            try:
                state.queue.task_done()
            except Exception:
                state.queue = asyncio.Queue()
        # Let the generic engine infer added count from items length delta
        return 0

    async def default_scroll() -> None:
        await _scroll_page_once(state.page, pause_ms=cfg.scroll_pause_ms)

    return await run_generic_collection(
        extra_params=extra_params,
        page=state.page,
        state=state,
        max_items=cfg.max_items,
        max_seconds=cfg.max_seconds,
        max_idle_rounds=cfg.max_idle_rounds,
        auto_scroll=cfg.auto_scroll,
        scroll_pause_ms=cfg.scroll_pause_ms,
        goto_first=goto_first,
        on_tick=on_tick,
        on_scroll=on_scroll or default_scroll,
        on_tick_start=on_tick_start,
        key_fn=key_fn,
    ) 