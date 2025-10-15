from __future__ import annotations

import asyncio


from src.config import get_logger
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, TypeVar

from playwright.async_api import Page

from .collection_common import scroll_page_once as _scroll_page_once
from src.utils.metrics import metrics
from ..common.plugin import StopDecision
from src.services.collection_common import CollectionState, ExitCondition, MaxItemsExit, TimeoutExit, IdleRoundsExit, ScrollBottomReachedExit

T = TypeVar("T")

OnTick = Callable[[], Awaitable[Optional[int]] | Optional[int]]

OnLoopItemStart = Callable[[int, Dict[str, Any], CollectionState], Awaitable[None]]
OnLoopItemCollected = Callable[[int, Dict[str, Any], int, List[T], CollectionState], Awaitable[None]]
OnLoopItemEnd = Callable[[int, Dict[str, Any], CollectionState], Awaitable[None]]

class CollectionLoopDelegate(Generic[T]):
    on_loop_item_start: Optional[OnLoopItemStart] = None
    on_loop_item_collected: Optional[OnLoopItemCollected[T]] = None
    on_loop_item_end: Optional[OnLoopItemEnd] = None

logger = get_logger(__name__)

async def run_generic_collection(
    *,
    extra_params: Optional[Dict[str, Any]] = None,
    page: Page,
    state: CollectionState,
    max_items: int,
    max_seconds: int,
    max_idle_rounds: int,
    auto_scroll: bool,
    scroll_pause_ms: int,
    goto_first: Optional[Callable[[], Awaitable[None]]] = None,
    on_tick: Optional[OnTick] = None,
    on_scroll: Optional[Callable[[], Awaitable[None]]] = None,
    delegate: CollectionLoopDelegate = CollectionLoopDelegate(),
) -> List[T]:

    """
    可扩展：未来可以加：
        RateLimitExit（采集速率限制）
        MemoryExit（内存溢出保护）
        PageCrashExit（页面崩溃检测）
    """
    exit_condition_list: List[ExitCondition] = [
        TimeoutExit(max_seconds),
        MaxItemsExit(max_items),
        IdleRoundsExit(max_idle_rounds),
    ]

    # Add ScrollBottomReachedExit only for infinite scroll (not for pager mode)
    # This detects when scrolling no longer changes page height
    scroll_mode = (extra_params or {}).get("scroll_mode")
    if scroll_mode != "pager":
        # Default threshold is 2 consecutive scrolls with no height change
        max_no_scroll_rounds = (extra_params or {}).get("max_no_scroll_rounds", 2)
        exit_condition_list.append(ScrollBottomReachedExit(max_consecutive=max_no_scroll_rounds))

    if goto_first:
        await goto_first()

    loop = asyncio.get_event_loop()
    start_ts = loop.time()
    idle_rounds = 0
    last_len = 0
    loop_count = 0
    need_break = False
    while True:
        loop_count += 1
        if delegate.on_loop_item_start:
            try:
                await delegate.on_loop_item_start(loop_count, extra_params, state)
            except Exception:
                pass
        elapsed = loop.time() - start_ts

        added = 0
        metrics.inc("collect.ticks")
        if on_tick:
            try:
                res = on_tick()
                added = await res if asyncio.iscoroutine(res) else int(res or 0)
            except Exception:
                added = 0

        if added == 0:
            new_len = len(state.items)
            if new_len > last_len:
                added = new_len - last_len
                last_len = new_len

        idle_rounds = 0 if added > 0 else idle_rounds + 1

        new_batch = state.items[last_len:new_len]

        if delegate.on_loop_item_collected:
            delegate.on_loop_item_collected(loop_count, extra_params, added, new_batch, state)

        for cond in exit_condition_list:
            stop_decision = await cond.should_exit(
                loop_count,
                extra_params,
                page,
                state,
                new_batch,
                idle_rounds,
                elapsed
            )
            if stop_decision.should_stop:
                metrics.event("collect.exit",
                              reason=stop_decision.reason,
                              details=stop_decision.details,
                              elapsed=elapsed)
                logger.info("collector.exit, should_stop=%s, stop_reason=%s, elapsed=%s",
                            stop_decision.should_stop, stop_decision.reason, elapsed)
                need_break = True

        if need_break: break

        if state.stop_decider:
            try:
                result = state.stop_decider(
                    loop_count,
                    extra_params,
                    page,
                    state,
                    new_batch,
                    idle_rounds,
                    elapsed,
                )
                stop_decision: StopDecision = await result if asyncio.iscoroutine(result) else result
                metrics.event("collector.stop_decider",
                              should_stop=stop_decision.should_stop,
                              stop_reason=stop_decision.reason,
                              elapsed=elapsed)
                logger.info("collector.stop_decider, should_stop=%s, stop_reason=%s, elapsed=%s",
                             stop_decision.should_stop, stop_decision.reason, elapsed)
                if stop_decision.should_stop:
                    break
            except Exception as e:
                logger.error(f"stop_decider execute failed: {str(e)}")

        if auto_scroll:
            if on_scroll:
                try:
                    await on_scroll()
                except Exception:
                    pass
            else:
                await _scroll_page_once(page, pause_ms=scroll_pause_ms)
            metrics.inc("collect.scrolls")

            # Detect scroll height changes for bottom detection
            # Only applicable for infinite scroll, not for pager mode
            try:
                current_height = await page.evaluate("document.documentElement.scrollHeight")
                if state.last_scroll_height is not None:
                    if current_height == state.last_scroll_height:
                        state.consecutive_no_height_change += 1
                        logger.debug(f"Scroll height unchanged: {current_height}, consecutive count: {state.consecutive_no_height_change}")
                    else:
                        state.consecutive_no_height_change = 0
                        logger.debug(f"Scroll height changed: {state.last_scroll_height} -> {current_height}")
                state.last_scroll_height = current_height
            except Exception as e:
                logger.debug(f"Failed to detect scroll height: {e}")

        if delegate.on_loop_item_end:
            await delegate.on_loop_item_end(loop_count, extra_params, state)
    # 退出时 break 掉了，末尾的 on_loop_item_end 没有执行，再执行一次来让调用次数一致
    if delegate.on_loop_item_end:
        await delegate.on_loop_item_end(loop_count, extra_params, state)

    return state.items.copy()
