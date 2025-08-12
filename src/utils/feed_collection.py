from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Sequence, TypeVar

from playwright.async_api import Page

from .net_rules import ResponseView
from .collection_common import scroll_page_once as _scroll_page_once, deduplicate_by as _deduplicate_by

T = TypeVar("T")

# Type of the user-provided stop decider
# page, all_raw_responses, last_raw_response, all_parsed_items, last_batch_parsed_items,
# elapsed_seconds, extra_config, last_response_view -> bool | Awaitable[bool]
StopDecider = Callable[[Page, List[Any], Optional[Any], List[T], List[T], float, Dict[str, Any], Optional[ResponseView]], bool | Awaitable[bool]]


@dataclass
class FeedCollectionConfig:
    """Configuration for network-driven feed collection.

    Attributes:
        max_items: Stop when collected at least this many items.
        max_seconds: Stop after this many seconds.
        max_idle_rounds: Stop after this many consecutive rounds with no new items.
        auto_scroll: Whether to scroll to bottom between rounds.
        scroll_pause_ms: Pause after each scroll, in milliseconds.
    """

    max_items: int = 1000
    max_seconds: int = 600
    max_idle_rounds: int = 2
    auto_scroll: bool = True
    scroll_pause_ms: int = 800


@dataclass
class FeedCollectionState(Generic[T]):
    """Mutable state for a feed collection session."""

    page: Page
    event: Optional[asyncio.Event] = None
    items: List[T] = field(default_factory=list)
    raw_responses: List[Any] = field(default_factory=list)
    last_raw_response: Optional[Any] = None
    last_response_view: Optional[ResponseView] = None
    stop_decider: Optional[StopDecider[T]] = None


def ensure_event(state: FeedCollectionState[Any]) -> None:
    """Ensure the state has an asyncio.Event for synchronization."""
    if state.event is None:
        state.event = asyncio.Event()


def reset_state(state: FeedCollectionState[Any]) -> None:
    """Reset dynamic fields of the state (items and responses)."""
    state.items.clear()
    state.raw_responses.clear()
    state.last_raw_response = None
    state.last_response_view = None
    if state.event is not None:
        try:
            state.event.clear()
        except Exception:
            state.event = asyncio.Event()


def record_response(state: FeedCollectionState[Any], data: Any, response_view: Optional[ResponseView] = None) -> None:
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
    state: FeedCollectionState[T],
    cfg: FeedCollectionConfig,
    *,
    extra_config: Optional[Dict[str, Any]] = None,
    goto_first: Optional[Callable[[], Awaitable[None]]] = None,
    on_scroll: Optional[Callable[[], Awaitable[None]]] = None,
    key_fn: Optional[Callable[[T], Optional[str]]] = None,
) -> List[T]:
    """Run a generic network-driven collection loop using provided state/config.

    Args:
        state: Shared mutable state (items will be populated externally by parser).
        cfg: Stop/scroll configuration.
        extra_config: Arbitrary config object passed to decider.
        goto_first: Optional coroutine to navigate to the starting page.
        on_scroll: Optional coroutine to run instead of default scroll action.
        key_fn: Optional key function for de-duplication (defaults to getattr(item, "id", None)).

    Returns:
        The list of collected items (deduplicated by key when provided).
    """
    ensure_event(state)
    reset_state(state)

    if goto_first:
        await goto_first()
        await asyncio.sleep(0.5)

    start_ts = asyncio.get_event_loop().time()
    last_len = 0
    idle_rounds = 0

    while True:
        elapsed = asyncio.get_event_loop().time() - start_ts
        if elapsed >= cfg.max_seconds:
            break
        if len(state.items) >= cfg.max_items:
            break

        try:
            await asyncio.wait_for(state.event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pass
        finally:
            try:
                state.event.clear()
            except Exception:
                state.event = asyncio.Event()

        new_len = len(state.items)
        if new_len > last_len:
            idle_rounds = 0
            new_items = state.items[last_len:new_len]
            if state.stop_decider:
                try:
                    result = state.stop_decider(
                        state.page,
                        state.raw_responses,
                        state.last_raw_response,
                        state.items,
                        new_items,
                        elapsed,
                        extra_config or {},
                        state.last_response_view,
                    )
                    should_stop = await result if asyncio.iscoroutine(result) else bool(result)
                    if should_stop:
                        break
                except Exception:
                    # Ignore decider errors
                    pass
            last_len = new_len
        else:
            idle_rounds += 1

        if idle_rounds >= cfg.max_idle_rounds:
            break

        if cfg.auto_scroll:
            if on_scroll:
                try:
                    await on_scroll()
                except Exception:
                    pass
            else:
                await _scroll_page_once(state.page, pause_ms=cfg.scroll_pause_ms)

    # Deduplicate
    if key_fn is None:
        key_fn = lambda it: getattr(it, "id", None)  # type: ignore[return-value]
    return _deduplicate_by(state.items, key_fn) 