from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, TypeVar

from playwright.async_api import Page

from .collection_common import scroll_page_once as _scroll_page_once, deduplicate_by as _deduplicate_by
from src.utils.metrics import metrics

T = TypeVar("T")

# Callback that performs one iteration "tick" and returns an optional explicit count of newly added items.
# If it returns None, the engine falls back to len(state.items) delta to determine progress.
OnTick = Callable[[], Awaitable[Optional[int]] | Optional[int]]


async def run_generic_collection(
    *,
    page: Page,
    state: Any,
    max_items: int,
    max_seconds: int,
    max_idle_rounds: int,
    auto_scroll: bool,
    scroll_pause_ms: int,
    goto_first: Optional[Callable[[], Awaitable[None]]] = None,
    on_tick: Optional[OnTick] = None,
    on_scroll: Optional[Callable[[], Awaitable[None]]] = None,
    key_fn: Optional[Callable[[T], Optional[str]]] = None,
) -> List[T]:
    if goto_first:
        await goto_first()
        await asyncio.sleep(0.5)

    loop = asyncio.get_event_loop()
    start_ts = loop.time()
    idle_rounds = 0
    last_len = 0

    while True:
        elapsed = loop.time() - start_ts
        if elapsed >= max_seconds:
            metrics.event("collect.exit", reason="timeout", elapsed=elapsed)
            break
        if len(state.items) >= max_items:
            metrics.event("collect.exit", reason="max_items", count=len(state.items))
            break

        added = 0
        metrics.inc("collect.ticks")
        if on_tick:
            try:
                res = on_tick()
                added = await res if asyncio.iscoroutine(res) else int(res or 0)
            except Exception:
                added = 0

        # If on_tick did not explicitly report added items, infer from length delta
        if added == 0:
            new_len = len(state.items)
            if new_len > last_len:
                added = new_len - last_len
                last_len = new_len

        if added > 0:
            idle_rounds = 0
        else:
            idle_rounds += 1

        if idle_rounds >= max_idle_rounds:
            metrics.event("collect.exit", reason="idle", idle_rounds=idle_rounds)
            logging.warning("超过最大空转轮数")
            break

        if auto_scroll:
            if on_scroll:
                try:
                    await on_scroll()
                except Exception:
                    pass
            else:
                await _scroll_page_once(page, pause_ms=scroll_pause_ms)
            metrics.inc("collect.scrolls")

    if key_fn is None:
        key_fn = lambda it: getattr(it, "id", None)  # type: ignore[return-value]
    return _deduplicate_by(state.items, key_fn)