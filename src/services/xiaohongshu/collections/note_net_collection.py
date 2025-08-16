from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, TypeVar

from playwright.async_api import Page

from src.utils.net_rules import ResponseView
from src.services.collection_common import scroll_page_once as _scroll_page_once, NetStopDecider
from src.services.collection_loop import run_generic_collection

T = TypeVar("T")

class NoteNetCollectionState(Generic[T]):
    """Mutable state for a note net collection session."""

    page: Page
    event: Optional[asyncio.Event] = None
    items: List[T] = field(default_factory=list)
    raw_responses: List[Any] = field(default_factory=list)
    last_raw_response: Optional[Any] = None
    last_response_view: Optional[ResponseView] = None
    stop_decider: Optional[NetStopDecider[T]] = None

    def __init__(self, page: Page, event: Optional[asyncio.Event], items: List[T] = field(default_factory=list),
                 raw_responses: List[Any] = field(default_factory=list), last_raw_response: Optional[Any] = None,
                 last_response_view: Optional[ResponseView] = None, stop_decider: Optional[NetStopDecider[T]] = None):
        self.page = page
        self.event = event
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

def ensure_event(state: NoteNetCollectionState[Any]) -> None:
    """Ensure the state has an asyncio.Event for synchronization."""
    if state.event is None:
        state.event = asyncio.Event()


def reset_state(state: NoteNetCollectionState[Any]) -> None:
    """Reset dynamic fields of the state (items and responses)."""
    state.clear()
    if state.event is not None:
        try:
            state.event.clear()
        except Exception:
            state.event = asyncio.Event()


def record_response(state: NoteNetCollectionState[Any], data: Any, response_view: Optional[ResponseView] = None) -> None:
    """Record a raw response and wake the collector loop."""
    try:
        state.raw_responses.append(data)
    except Exception:
        pass
    state.last_raw_response = data
    state.last_response_view = response_view
    if state.event is not None:
        try:
            state.event.set()
        except Exception:
            pass


async def run_network_collection(
    state: NoteNetCollectionState[T],
    cfg: "ServiceConfig",
    *,
    extra_config: Optional[Dict[str, Any]] = None,
    goto_first: Optional[Callable[[], Awaitable[None]]] = None,
    on_scroll: Optional[Callable[[], Awaitable[None]]] = None,
    on_tick_start: Optional[Callable[[int, Dict[str, Any]], Awaitable[None]]] = None,
    key_fn: Optional[Callable[[T], Optional[str]]] = None,
) -> List[T]:
    """Run a unified network-driven collection loop using the generic engine.

    This function assumes external code populates state.items and state.event is
    set when new items arrive (e.g., via NetRuleBus consumer). It converts that
    contract into a generic on_tick callback that waits for the event.
    """
    ensure_event(state)
    reset_state(state)

    async def on_tick() -> Optional[int]:
        # Wait for event with a short timeout to allow idle detection
        try:
            await asyncio.wait_for(state.event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            logging.debug("network collection timed out")
            return 0
        finally:
            try:
                state.event.clear()
            except Exception:
                state.event = asyncio.Event()
        # Let the generic engine infer added count from items length delta
        return 0

    async def default_scroll() -> None:
        await _scroll_page_once(state.page, pause_ms=cfg.scroll_pause_ms)

    return await run_generic_collection(
        extra_config=extra_config,
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