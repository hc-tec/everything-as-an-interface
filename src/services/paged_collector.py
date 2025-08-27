from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, TypeVar

from playwright.async_api import Page

from src.services.net_collection_loop import NetCollectionState, record_response
from src.utils.net_rules import ResponseView
from src.utils.metrics import metrics

T = TypeVar("T")

# Parser signature: payload(dict) -> List[T]
ParserFn = Callable[[Dict[str, Any]], Awaitable[List[T]] | List[T]]

# Stop decider signature is reused from Note utils via state.stop_decider


class PagedCollector(Generic[T]):
    """A reusable paginated collector built on top of an asyncio.Queue of ResponseView.

    It integrates:
      - Response queue consumption (produced by NetRuleBus)
      - Recording raw responses into NetCollectionState
      - Optional stop_decider on the state
      - Delegate-like hooks via callbacks
    """

    def __init__(
        self,
        *,
        page: Page,
        queue: asyncio.Queue,
        state: NetCollectionState[T],
        parser: ParserFn[T],
        response_timeout_sec: float = 5.0,
        delay_ms: int = 500,
        max_pages: Optional[int] = None,
        on_response: Optional[Callable[[ResponseView, NetCollectionState[T]], Awaitable[None] | None]] = None,
        on_items_collected: Optional[Callable[[List[T], NetCollectionState[T]], Awaitable[List[T]] | List[T]]] = None,
    ) -> None:
        self.page = page
        self.queue = queue
        self.state = state
        self.parser = parser
        self.response_timeout_sec = float(response_timeout_sec)
        self.delay_ms = int(delay_ms)
        self.max_pages = max_pages
        self.on_response = on_response
        self.on_items_collected = on_items_collected

    async def run(self, *, extra_params: Optional[Dict[str, Any]] = None) -> List[T]:
        extra: Dict[str, Any] = dict(extra_params or {})
        items: List[T] = []
        start = time.monotonic()
        pages = 0
        last_len = 0

        while True:
            if self.max_pages is not None and pages >= self.max_pages:
                break

            try:
                rv: ResponseView = await asyncio.wait_for(self.queue.get(), timeout=self.response_timeout_sec)
            except asyncio.TimeoutError:
                break

            metrics.inc("collector.queue_pop")
            # Hook: on_response
            if self.on_response:
                try:
                    ret = self.on_response(rv, self.state)
                    if asyncio.iscoroutine(ret):
                        await ret
                except Exception:
                    pass

            payload = rv.data()
            if not isinstance(payload, dict):
                continue

            # Record raw response into state
            try:
                record_response(self.state, payload, rv)
                metrics.inc("collector.record_response")
            except Exception:
                pass

            # Parse batch
            batch: List[T] = []
            try:
                parsed = self.parser(payload)
                batch = await parsed if asyncio.iscoroutine(parsed) else parsed
                metrics.inc("collector.parsed_count", len(batch))
            except Exception:
                batch = []

            # Hook: on_items_collected
            if batch and self.on_items_collected:
                try:
                    processed = self.on_items_collected(batch, self.state)
                    batch = await processed if asyncio.iscoroutine(processed) else processed
                except Exception:
                    pass

            # Append
            if batch:
                items.extend(batch)
                try:
                    self.state.items.extend(batch)
                except Exception:
                    pass
                if self.state.queue:
                    try:
                       await self.state.queue.put(batch)
                    except Exception:
                        pass

            # Stop-decider
            new_len = len(items)
            if self.state.stop_decider:
                try:
                    elapsed = time.monotonic() - start
                    new_batch = items[last_len:new_len]
                    result = self.state.stop_decider(
                        self.page,
                        self.state.raw_responses,
                        self.state.last_raw_response,
                        items,
                        new_batch,
                        elapsed,
                        extra,
                        self.state.last_response_view,
                    )
                    should_stop = await result if asyncio.iscoroutine(result) else bool(result)
                    metrics.event("collector.stop_decider", should_stop=should_stop, elapsed=elapsed)
                    if should_stop:
                        break
                except Exception:
                    pass
            last_len = new_len

            pages += 1
            # Delay between pages
            if self.delay_ms > 0:
                await asyncio.sleep(max(0.01, float(self.delay_ms) / 1000.0))

        return items