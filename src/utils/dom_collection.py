from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Sequence, TypeVar

from playwright.async_api import Page

T = TypeVar("T")

ExtractOnce = Callable[[Page, List[T]], Awaitable[int] | int]
KeyFn = Callable[[T], Optional[str]]

from .collection_common import scroll_page_once as _scroll_page_once, deduplicate_by as _deduplicate_by

@dataclass
class DomCollectionConfig:
    max_items: int = 1000
    max_seconds: int = 600
    max_idle_rounds: int = 2
    auto_scroll: bool = True
    scroll_pause_ms: int = 800


@dataclass
class DomCollectionState(Generic[T]):
    page: Page
    items: List[T] = field(default_factory=list)


async def run_dom_collection(
    state: DomCollectionState[T],
    cfg: DomCollectionConfig,
    *,
    goto_first: Optional[Callable[[], Awaitable[None]]] = None,
    extract_once: ExtractOnce[T] = None,
    key_fn: Optional[KeyFn[T]] = None,
) -> List[T]:
    if goto_first:
        await goto_first()
        await asyncio.sleep(0.5)

    start_ts = asyncio.get_event_loop().time()
    idle_rounds = 0

    while True:
        elapsed = asyncio.get_event_loop().time() - start_ts
        if elapsed >= cfg.max_seconds:
            break
        if len(state.items) >= cfg.max_items:
            break

        added = 0
        if extract_once:
            try:
                ret = extract_once(state.page, state.items)
                added = await ret if asyncio.iscoroutine(ret) else int(ret or 0)
            except Exception:
                added = 0
        if added > 0:
            idle_rounds = 0
        else:
            idle_rounds += 1

        if idle_rounds >= cfg.max_idle_rounds:
            break

        if cfg.auto_scroll:
            increased = await _scroll_page_once(state.page, pause_ms=cfg.scroll_pause_ms)
            if not increased:
                idle_rounds += 1

    if key_fn is None:
        key_fn = lambda it: getattr(it, "id", None)  # type: ignore[return-value]
    return _deduplicate_by(state.items, key_fn) 