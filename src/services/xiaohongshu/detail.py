from __future__ import annotations

import asyncio
import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Generic, TypeVar

from playwright.async_api import Page

from src.services.base import BaseSiteService, ServiceDelegate
from src.utils.net_rule_bus import NetRuleBus
from src.services.xiaohongshu.models import NoteDetail, SearchAuthor
from src.utils.net_rules import ResponseView

logger = logging.getLogger(__name__)

T = TypeVar("T")

@dataclass
class DetailArgs:
    """Arguments for detail fetching tasks."""

    item_id: str
    extra_config: Optional[Dict[str, Any]] = None


class DetailServiceDelegate(Generic[T]):
    """Optional delegate hooks for detail service."""

    async def on_attach(self, page: Page) -> None:  # pragma: no cover - default no-op
        return None

    async def on_detach(self) -> None:  # pragma: no cover - default no-op
        return None

    async def before_navigate(self, item_id: str) -> None:  # pragma: no cover - default no-op
        return None

    async def on_response(self, response: ResponseView) -> None:  # pragma: no cover - default no-op
        return None

    async def parse_detail(self, item_id: str, payload: Dict[str, Any]) -> Optional[T]:  # pragma: no cover - default None
        return None


class DetailService(BaseSiteService, Generic[T]):
    """Interface for fetching detailed information about specific items."""

    def __init__(self) -> None:
        super().__init__()
        self.page: Optional[Page] = None
        self._delegate: Optional[ServiceDelegate[T]] = None

    def set_delegate(self, delegate: Optional[ServiceDelegate[T]]) -> None:  # pragma: no cover - simple setter
        self._delegate = delegate

    @abstractmethod
    async def get_detail(self, args: DetailArgs) -> Optional[T]:
        """Fetch detailed information for a specific item."""
        ...

    @abstractmethod
    async def get_details_batch(self, item_ids: List[str], *, extra_config: Optional[Dict[str, Any]] = None) -> List[
        Optional[T]]:
        """Fetch details for multiple items efficiently."""
        ...


class XiaohongshuDetailService(DetailService[NoteDetail]):
    """Service for fetching detailed information about Xiaohongshu notes."""

    def __init__(self) -> None:
        super().__init__()
        self.page: Optional[Page] = None
        self.bus = NetRuleBus()
        self._detail_queue = None
        self._cache: Dict[str, NoteDetail] = {}

    async def attach(self, page: Page) -> None:
        """Attach the service to a Page and bind network rules."""
        self.page = page
        self._unbind = await self.bus.bind(page)
        # Subscribe to note detail API responses
        self._detail_queue = self.bus.subscribe(r".*/feed", kind="response")
        if self._delegate:
            try:
                await self._delegate.on_attach(page)
            except Exception:
                pass

    async def detach(self) -> None:
        if self._delegate:
            try:
                await self._delegate.on_detach()
            except Exception:
                pass
        await super().detach()

    async def get_detail(self, args: DetailArgs) -> Optional[NoteDetail]:
        """
        Fetch detailed information for a specific note.
        
        Args:
            args: Detail arguments containing note ID and extra config
            
        Returns:
            NoteDetail object if successful, None otherwise
        """
        if not self.page or not self._detail_queue:
            raise RuntimeError("Service not attached to a Page")

        note_id = args.item_id
        
        # Check cache first
        if note_id in self._cache:
            logger.debug(f"Returning cached detail for note {note_id}")
            return self._cache[note_id]

        try:
            # Navigate to the note detail page to trigger API calls
            if self._delegate:
                try:
                    await self._delegate.before_navigate(note_id)
                except Exception:
                    pass
            await self._navigate_to_note(note_id)
            
            # Wait for detail response
            default_to = self._service_config.response_timeout_sec or 10.0
            timeout = args.extra_config.get("timeout", default_to) if args.extra_config else default_to
            try:
                response_view: ResponseView = await asyncio.wait_for(self._detail_queue.get(), timeout=timeout)
                if self._delegate:
                    try:
                        await self._delegate.on_response(response_view)
                    except Exception:
                        pass
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for detail response for note {note_id}")
                return None

            # Parse the response
            data = response_view.data()
            detail = None
            if self._delegate:
                try:
                    detail = await self._delegate.parse_single(note_id, data)
                except Exception:
                    detail = None
            if detail is None:
                detail = await self._parse_detail_response(note_id, data)
            
            if detail:
                self._cache[note_id] = detail
                logger.info(f"Successfully fetched detail for note {note_id}")
            
            return detail

        except Exception as e:
            logger.error(f"Error fetching detail for note {note_id}: {e}")
            return None

    async def get_details_batch(
        self, 
        item_ids: List[str], 
        *, 
        extra_config: Optional[Dict[str, Any]] = None
    ) -> List[Optional[NoteDetail]]:
        """
        Fetch details for multiple notes efficiently.
        
        Args:
            item_ids: List of note IDs to fetch
            extra_config: Extra configuration options
            
        Returns:
            List of NoteDetail objects (None for failed fetches)
        """
        results: List[Optional[NoteDetail]] = []
        delay_ms = extra_config.get("delay_ms", 500) if extra_config else 500
        
        for note_id in item_ids:
            detail_args = DetailArgs(item_id=note_id, extra_config=extra_config)
            detail = await self.get_detail(detail_args)
            results.append(detail)
            
            # Add delay between requests to avoid rate limiting
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000.0)
                
        return results

    async def _navigate_to_note(self, note_id: str) -> None:
        """Navigate to a specific note's detail page."""
        if not self.page:
            return
            
        try:
            # Construct the note URL - adjust based on actual site structure
            note_url = f"https://www.xiaohongshu.com/explore/{note_id}"
            await self.page.goto(note_url, wait_until="load")
            # Give some time for dynamic content to load
            await asyncio.sleep(1.0)
        except Exception as e:
            logger.warning(f"Failed to navigate to note {note_id}: {e}")

    async def _parse_detail_response(self, note_id: str, payload: Dict[str, Any]) -> Optional[NoteDetail]:
        """
        Parse the API response to extract note detail information.
        
        Args:
            note_id: The note ID
            payload: Raw API response data
            
        Returns:
            Parsed NoteDetail object or None if parsing fails
        """
        try:
            if not payload or payload.get("code") != 0:
                return None

            data = payload.get("data", {})
            note_info = data.get("note_detail", {}) or data.get("items", [{}])[0]
            
            if not note_info:
                return None

            # Extract basic info
            title = str(note_info.get("title", ""))
            content = str(note_info.get("desc", "") or note_info.get("content", ""))
            
            # Extract author information
            user_info = note_info.get("user", {})
            author = SearchAuthor(
                user_id=str(user_info.get("user_id", "")),
                username=str(user_info.get("nickname", "")),
                avatar=str(user_info.get("avatar", ""))
            )

            # Extract tags
            tags = []
            tag_list = note_info.get("tag_list", []) or note_info.get("tags", [])
            for tag in tag_list:
                if isinstance(tag, dict):
                    tag_name = tag.get("name", "")
                else:
                    tag_name = str(tag)
                if tag_name:
                    tags.append(tag_name)

            # Extract media
            images = []
            image_list = note_info.get("image_list", [])
            for img in image_list:
                if isinstance(img, dict):
                    url = img.get("url_default") or img.get("url") or img.get("live_photo", {}).get("url")
                    if url:
                        images.append(str(url))
                elif isinstance(img, str):
                    images.append(img)

            video = None
            video_info = note_info.get("video", {})
            if video_info:
                video = str(video_info.get("url", "") or video_info.get("master_url", ""))

            # Extract interaction data
            interact_info = note_info.get("interact_info", {})
            like_count = int(interact_info.get("liked_count", 0))
            collect_count = int(interact_info.get("collected_count", 0)) 
            comment_count = int(interact_info.get("comment_count", 0))
            share_count = int(interact_info.get("share_count", 0))
            view_count = interact_info.get("view_count")
            if view_count is not None:
                view_count = int(view_count)

            # Extract timestamps and metadata
            created_at = str(note_info.get("time", "") or note_info.get("create_time", ""))
            updated_at = note_info.get("last_update_time")
            if updated_at:
                updated_at = str(updated_at)

            ip_location = note_info.get("ip_location")
            if ip_location:
                ip_location = str(ip_location)

            note_type = str(note_info.get("type", "normal"))
            visibility = "public"  # Default, could be extracted from other fields
            
            topic = note_info.get("topic")
            if topic:
                topic = str(topic)
                
            location = note_info.get("location")
            if location:
                location = str(location)
                
            music = note_info.get("music")
            if music:
                music = str(music)

            return NoteDetail(
                id=note_id,
                title=title,
                content=content,
                author=author,
                tags=tags,
                images=images,
                video=video,
                like_count=like_count,
                collect_count=collect_count,
                comment_count=comment_count,
                share_count=share_count,
                view_count=view_count,
                created_at=created_at,
                updated_at=updated_at,
                ip_location=ip_location,
                note_type=note_type,
                visibility=visibility,
                topic=topic,
                location=location,
                music=music,
                extra_data=note_info  # Store raw data for debugging
            )

        except Exception as e:
            logger.error(f"Error parsing detail response for note {note_id}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the detail cache."""
        self._cache.clear()
        logger.debug("Detail cache cleared")

    def get_cache_size(self) -> int:
        """Get the current cache size."""
        return len(self._cache)
