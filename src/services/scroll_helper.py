from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from playwright.async_api import Page

from src.services.base_service import ServiceConfig
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
        service_config: ServiceConfig,
        pause_ms: int,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Callable[[], Awaitable[None]]:
        async def on_scroll() -> None:
            try:
                strat: ScrollStrategy
                # Prefer ServiceConfig if specified
                if service_config.scroll_mode == "selector" and service_config.scroll_selector:
                    strat = SelectorScrollStrategy(service_config.scroll_selector, pause_ms=pause_ms)
                elif service_config.scroll_mode == "pager" and service_config.pager_selector:
                    strat = PagerClickStrategy(service_config.pager_selector, wait_ms=pause_ms)
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

