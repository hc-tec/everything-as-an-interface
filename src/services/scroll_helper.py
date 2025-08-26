from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from playwright.async_api import Page

from src.services.base_service import ServiceParams
from src.utils.scrolling import (
    DefaultScrollStrategy,
    PagerClickStrategy,
    ScrollStrategy,
    SelectorScrollStrategy,
)


@dataclass
class ScrollHelper:
    """Factory for building on_scroll coroutine based on config/extra."""

    @staticmethod
    def build_on_scroll(
        page: Page,
        *,
        service_params: ServiceParams,
        pause_ms: int,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Callable[[], Awaitable[None]]:
        async def on_scroll() -> None:
            try:
                strat: ScrollStrategy
                # Prefer ServiceParams if specified
                if service_params.scroll_mode == "selector" and service_params.scroll_selector:
                    strat = SelectorScrollStrategy(service_params.scroll_selector, pause_ms=pause_ms)
                elif service_params.scroll_mode == "pager" and service_params.pager_selector:
                    strat = PagerClickStrategy(service_params.pager_selector, wait_ms=pause_ms)
                else:
                    ex = (extra or {})
                    if ex.get("scroll_selector"):
                        strat = SelectorScrollStrategy(ex["scroll_selector"], pause_ms=pause_ms)
                    elif ex.get("pager_selector"):
                        strat = PagerClickStrategy(ex["pager_selector"], wait_ms=pause_ms)
                    else:
                        strat = DefaultScrollStrategy(pause_ms=pause_ms)
                await strat.scroll(page)
            except Exception:
                pass

        return on_scroll

