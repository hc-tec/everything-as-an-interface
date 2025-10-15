from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional, Sequence, TypeVar, Dict, Awaitable, Generic

from playwright.async_api import Page

from src.common.plugin import StopDecision
from src.utils.net_rules import ResponseView

T = TypeVar("T")

# Type of the user-provided stop decider
# (loop_count, extra_params, page, state, new_batch, idle_rounds, elapsed) -> StopDecision:
StopDecider = Callable[[int, Dict[str, Any], Page, Any, List[T], int, float], StopDecision | Awaitable[StopDecision]]

class CollectionState(Generic[T]):
    """Mutable state for a note net collection session."""

    page: Page
    items: List[T] = []
    stop_decider: Optional[StopDecider[T]] = None
    # Scroll height tracking for bottom detection
    last_scroll_height: Optional[int] = None
    consecutive_no_height_change: int = 0

    def __init__(self, page: Page, items=None, stop_decider: Optional[StopDecider[T]] = None):
        if items is None:
            items = []
        self.page = page
        self.items = items
        self.stop_decider = stop_decider
        self.last_scroll_height = None
        self.consecutive_no_height_change = 0

    def clear(self):
        self.items = []
        self.last_scroll_height = None
        self.consecutive_no_height_change = 0

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

class ExitCondition(ABC, Generic[T]):
    @abstractmethod
    async def should_exit(self,
                    loop_count: int,
                    extra_params: Dict[str, Any],
                    page: Page,
                    state: Any,
                    new_batch: List[T],
                    idle_rounds: int,
                    elapsed: float) -> StopDecision:
        """Return reason string if should exit, else None."""

class TimeoutExit(ExitCondition, Generic[T]):
    def __init__(self, max_seconds: int): self.max_seconds = max_seconds
    async def should_exit(self,
                    loop_count: int,
                    extra_params: Dict[str, Any],
                    page: Page,
                    state: Any,
                    new_batch: List[T],
                    idle_rounds: int,
                    elapsed: float) -> StopDecision:
        if elapsed >= self.max_seconds:
            return StopDecision(should_stop=True, reason="timeout", details={})
        return StopDecision(should_stop=False, reason="not timeout", details={})

class MaxItemsExit(ExitCondition, Generic[T]):
    def __init__(self, max_items: int): self.max_items = max_items
    async def should_exit(self,
                    loop_count: int,
                    extra_params: Dict[str, Any],
                    page: Page,
                    state: Any,
                    new_batch: List[T],
                    idle_rounds: int,
                    elapsed: float) -> StopDecision:
        if len(state.items) >= self.max_items:
            return StopDecision(should_stop=True, reason="max_items",
                                details={"max_items": self.max_items, "current_items": len(state.items)})
        return StopDecision(should_stop=False, reason="not max_items", details={})


class IdleRoundsExit(ExitCondition, Generic[T]):
    def __init__(self, max_idle_rounds: int): self.max_idle_rounds = max_idle_rounds
    async def should_exit(self,
                    loop_count: int,
                    extra_params: Dict[str, Any],
                    page: Page,
                    state: Any,
                    new_batch: List[T],
                    idle_rounds: int,
                    elapsed: float) -> StopDecision:
        if idle_rounds >= self.max_idle_rounds:
            return StopDecision(should_stop=True, reason="max_idle_rounds",
                                details={"max_idle_rounds": self.max_idle_rounds})
        return StopDecision(should_stop=False, reason="not max_items", details={})


class ScrollBottomReachedExit(ExitCondition, Generic[T]):
    """Exit condition for detecting when scrolling reaches page bottom.

    This condition detects when the page scroll height stops changing after
    consecutive scroll attempts, indicating the bottom has been reached.

    Note: This is only applicable for infinite scroll / waterfall layouts.
    For paginated content, use IdleRoundsExit instead.
    """
    def __init__(self, max_consecutive: int = 2):
        """Initialize the exit condition.

        Args:
            max_consecutive: Maximum number of consecutive scrolls with no height
                           change before considering bottom reached. Default is 2.
        """
        self.max_consecutive = max_consecutive

    async def should_exit(self,
                    loop_count: int,
                    extra_params: Dict[str, Any],
                    page: Page,
                    state: Any,
                    new_batch: List[T],
                    idle_rounds: int,
                    elapsed: float) -> StopDecision:
        """Check if scroll bottom has been reached.

        Returns:
            StopDecision indicating whether to stop and reason.
        """
        if hasattr(state, 'consecutive_no_height_change'):
            if state.consecutive_no_height_change >= self.max_consecutive:
                return StopDecision(
                    should_stop=True,
                    reason="scroll_bottom_reached",
                    details={
                        "consecutive_no_height_change": state.consecutive_no_height_change,
                        "threshold": self.max_consecutive
                    }
                )
        return StopDecision(should_stop=False, reason="not at bottom", details={})
