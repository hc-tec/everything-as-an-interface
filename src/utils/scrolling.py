from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Optional

from playwright.async_api import Page


class ScrollStrategy(ABC):
    @abstractmethod
    async def scroll(self, page: Page) -> None:
        ...


class DefaultScrollStrategy(ScrollStrategy):
    def __init__(self, *, pause_ms: int = 800) -> None:
        self.pause_ms = pause_ms

    async def scroll(self, page: Page) -> None:
        try:
            await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            await asyncio.sleep(max(0.05, float(self.pause_ms) / 1000.0))
        except Exception:
            pass


class SelectorScrollStrategy(ScrollStrategy):
    def __init__(self, selector: str, *, pause_ms: int = 800) -> None:
        self.selector = selector
        self.pause_ms = pause_ms

    async def scroll(self, page: Page) -> None:
        try:
            await page.evaluate(
                "(sel) => { const el = document.querySelector(sel); if (el) el.scrollTop = el.scrollHeight; }",
                self.selector,
            )
            await asyncio.sleep(max(0.05, float(self.pause_ms) / 1000.0))
        except Exception:
            pass


class PagerClickStrategy(ScrollStrategy):
    def __init__(self, selector: str, *, wait_ms: int = 800) -> None:
        self.selector = selector
        self.wait_ms = wait_ms

    async def scroll(self, page: Page) -> None:
        try:
            await page.click(self.selector)
        except Exception:
            pass
        await asyncio.sleep(max(0.05, float(self.wait_ms) / 1000.0))