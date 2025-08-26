from __future__ import annotations

import asyncio
from typing import Any, Callable, List, Optional, Sequence, TypeVar, Dict, Awaitable

from playwright.async_api import Page

from src.common.plugin import StopDecision
from src.utils.net_rules import ResponseView

T = TypeVar("T")

# Type of the user-provided stop decider
# (loop_count, extra_params, page, state, new_batch, elapsed) -> StopDecision:
NetStopDecider = Callable[[int, Dict[str, Any], Page, Any, List[T], float], StopDecision | Awaitable[StopDecision]]


async def scroll_page_once(page: Page, *, pause_ms: int = 800) -> bool:
    """Scroll the page once and return True if the scroll height increased."""
    try:
        last_height = await page.evaluate("document.documentElement.scrollHeight")
        await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        await asyncio.sleep(max(0.05, float(pause_ms) / 1000.0))
        new_height = await page.evaluate("document.documentElement.scrollHeight")
        return bool(new_height and last_height and new_height > last_height)
    except Exception:
        return False


def deduplicate_by(items: Sequence[T], key_fn: Callable[[T], Optional[str]]) -> List[T]:
    """Return a new list with items deduplicated by key_fn, keeping order."""
    seen: set[str] = set()
    results: List[T] = []
    for it in items:
        try:
            key = key_fn(it)
        except Exception:
            key = None
        if not key or key in seen:
            continue
        seen.add(key)
        results.append(it)
    return results