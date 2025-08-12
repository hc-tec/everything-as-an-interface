from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Sequence, TypeVar

from playwright.async_api import Page

T = TypeVar("T")

ExtractOnce = Callable[[Page, List[T]], Awaitable[int] | int]
KeyFn = Callable[[T], Optional[str]]

from .collection_common import scroll_page_once as _scroll_page_once, deduplicate_by as _deduplicate_by
from .collection_loop import run_generic_collection

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
    async def on_tick() -> Optional[int]:
        if not extract_once:
            return 0
        try:
            ret = extract_once(state.page, state.items)
            return await ret if asyncio.iscoroutine(ret) else int(ret or 0)
        except Exception:
            return 0

    return await run_generic_collection(
        page=state.page,
        state_items=state.items,
        max_items=cfg.max_items,
        max_seconds=cfg.max_seconds,
        max_idle_rounds=cfg.max_idle_rounds,
        auto_scroll=cfg.auto_scroll,
        scroll_pause_ms=cfg.scroll_pause_ms,
        goto_first=goto_first,
        on_tick=on_tick,
        key_fn=key_fn,
    ) 