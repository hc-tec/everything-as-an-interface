from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, TypeVar

from playwright.async_api import Page

from src.utils.feed_collection import FeedCollectionConfig, FeedCollectionState
from src.utils.net_rules import ResponseView

T = TypeVar("T")

StopDecider = Callable[[Page, List[Any], Optional[Any], List[T], List[T], float, Dict[str, Any], Optional[ResponseView]], bool | Awaitable[bool]]


class BaseSiteService(ABC):
    """Base for all site services (feed/detail/publish etc.)."""

    def __init__(self) -> None:
        self._unbind: Optional[Callable[[], None]] = None

    @abstractmethod
    async def attach(self, page: Page) -> None:
        """Attach the service onto a Page (bind network rules, init state)."""
        ...

    async def detach(self) -> None:
        unbind = self._unbind
        self._unbind = None
        if unbind:
            try:
                unbind()
            except Exception:
                pass


@dataclass
class FeedCollectArgs:
    """Arguments for a standard feed collection task."""

    goto_first: Optional[Callable[[], Awaitable[None]]] = None
    extra_config: Optional[Dict[str, Any]] = None


class FeedService(BaseSiteService, Generic[T]):
    """Interface for site feed service implementations."""

    def __init__(self) -> None:
        super().__init__()
        self.page: Optional[Page] = None
        self.state: Optional[FeedCollectionState[T]] = None

    @abstractmethod
    def set_stop_decider(self, decider: Optional[StopDecider[T]]) -> None:  # pragma: no cover - interface
        ...

    @abstractmethod
    def configure(self, cfg: FeedCollectionConfig) -> None:  # pragma: no cover - interface
        ...

    @abstractmethod
    async def collect(self, args: FeedCollectArgs) -> List[T]:  # pragma: no cover - interface
        ... 