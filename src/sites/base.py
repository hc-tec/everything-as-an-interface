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


@dataclass
class ServiceConfig:
    """Common configuration for site services.

    Attributes:
        response_timeout_sec: Max seconds to wait for a response event.
        delay_ms: Delay between pages/batches/polls (when applicable).
        queue_maxsize: Optional queue size hint for internal buffers.
        concurrency: Desired concurrency for request generation (advisory).
        max_pages: Optional page limit for paginated collectors.
    """

    response_timeout_sec: float = 5.0
    delay_ms: int = 500
    queue_maxsize: Optional[int] = None
    concurrency: int = 1
    max_pages: Optional[int] = None


class BaseSiteService(ABC):
    """Base for all site services (feed/detail/publish etc.)."""

    def __init__(self) -> None:
        self._unbind: Optional[Callable[[], None]] = None
        self._service_config: ServiceConfig = ServiceConfig()

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

    def set_service_config(self, cfg: ServiceConfig) -> None:  # pragma: no cover - simple setter
        self._service_config = cfg


# Delegate interfaces for service customization
class FeedServiceDelegate(Generic[T], ABC):
    """Optional delegate that can customize network-driven feed collection.

    Users can provide a delegate to override or extend default behaviors.
    All methods are optional to implement; default implementations are no-ops
    and keep the built-in behavior.
    """

    async def on_attach(self, page: Page) -> None:  # pragma: no cover - default no-op
        return None

    async def on_detach(self) -> None:  # pragma: no cover - default no-op
        return None

    async def on_response(self, response: ResponseView, state: FeedCollectionState[T]) -> None:  # pragma: no cover - default no-op
        """Called when a matching network response arrives before default parsing."""
        return None

    def should_record_response(self, payload: Any, response_view: ResponseView) -> bool:  # pragma: no cover - default yes
        """Whether to record this payload into the state before parsing."""
        return True

    async def parse_feed_items(self, payload: Dict[str, Any]) -> Optional[List[T]]:  # pragma: no cover - default None
        """Return parsed items from payload. Return None to use default parser."""
        return None

    async def on_items_collected(self, items: List[T], state: FeedCollectionState[T]) -> List[T]:  # pragma: no cover - default passthrough
        """Post-process parsed items (filter/transform) before appending to state."""
        return items


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
        # Optional delegate for customization
        self._delegate: Optional[FeedServiceDelegate[T]] = None

    def set_delegate(self, delegate: Optional[FeedServiceDelegate[T]]) -> None:  # pragma: no cover - simple setter
        """Install or clear a delegate for customizing feed behavior."""
        self._delegate = delegate
        # If already attached, allow delegate to observe attachment
        if delegate and self.page:
            try:
                asyncio.create_task(delegate.on_attach(self.page))
            except Exception:
                pass

    @abstractmethod
    def set_stop_decider(self, decider: Optional[StopDecider[T]]) -> None:  # pragma: no cover - interface
        ...

    @abstractmethod
    def configure(self, cfg: FeedCollectionConfig) -> None:  # pragma: no cover - interface
        ...

    @abstractmethod
    async def collect(self, args: FeedCollectArgs) -> List[T]:  # pragma: no cover - interface
        ...




@dataclass
class PublishContent:
    """Content to be published."""

    title: str
    content: str
    images: Optional[List[str]] = None  # Local file paths or URLs
    video: Optional[str] = None  # Local file path or URL
    tags: Optional[List[str]] = None
    visibility: str = "public"  # public, private, friends_only
    extra_config: Optional[Dict[str, Any]] = None


@dataclass
class PublishResult:
    """Result of a publish operation."""

    success: bool
    item_id: Optional[str] = None
    url: Optional[str] = None
    error_message: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


class PublishService(BaseSiteService):
    """Interface for publishing content to a site."""

    def __init__(self) -> None:
        super().__init__()
        self.page: Optional[Page] = None

    @abstractmethod
    async def publish(self, content: PublishContent) -> PublishResult:
        """Publish content to the site."""
        ...

    @abstractmethod
    async def save_draft(self, content: PublishContent) -> PublishResult:
        """Save content as a draft."""
        ...

    @abstractmethod
    async def get_publish_status(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Check the status of a published item."""
        ...