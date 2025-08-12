"""
Xiaohongshu Plugin V2 - Service-based Architecture

This is a thin plugin that orchestrates calls to various Xiaohongshu site services.
The plugin focuses on configuration, coordination, and output formatting,
while delegating specific tasks to specialized services.
"""

import asyncio
import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from src.core.plugin_context import PluginContext
from src.core.task_config import TaskConfig
from src.plugins.base import BasePlugin
from src.plugins.registry import register_plugin
from src.sites.base import FeedCollectArgs
from src.sites.xiaohongshu import (
    XiaohongshuCommentService,
    XiaohongshuFeedService,
)
from src.sites.xiaohongshu.detail import XiaohongshuDetailService
from src.utils.feed_collection import FeedCollectionConfig

logger = logging.getLogger("plugin.xiaohongshu_v2")

PLUGIN_ID = "xiaohongshu_v2"
PLUGIN_VERSION = "2.0.0"


class XiaohongshuV2Plugin(BasePlugin):
    """
    Xiaohongshu Plugin V2 - Thin orchestration layer using site services.
    
    This plugin demonstrates the service-based architecture where:
    - Plugin handles configuration and orchestration
    - Services handle site-specific logic and data collection
    - Plugin formats and returns results
    """

    def __init__(self) -> None:
        super().__init__()
        self.plugin_id = PLUGIN_ID
        self.version = PLUGIN_VERSION
        self.description = "Xiaohongshu automation plugin (service-based v2)"
        
        # Initialize services (will be attached during setup)
        self._feed_service: Optional[XiaohongshuFeedService] = None
        self._comment_service: Optional[XiaohongshuCommentService] = None


    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            # Initialize services
            self._feed_service = XiaohongshuFeedService()
            self._detail_service = XiaohongshuDetailService()
            self._comment_service = XiaohongshuCommentService()

            # Attach all services to the page
            await self._feed_service.attach(self.page)
            await self._detail_service.attach(self.page)
            await self._comment_service.attach(self.page)

            # Configure feed service based on task config
            feed_config = self._build_feed_config()
            self._feed_service.configure(feed_config)

            # Set custom stop conditions if specified
            stop_decider = self._build_stop_decider()
            if stop_decider:
                self._feed_service.set_stop_decider(stop_decider)

            logger.info("All Xiaohongshu services initialized and attached")

        except Exception as e:
            logger.error(f"Service setup failed: {e}")
            raise
        logger.info("启动小红书插件")
        return await super().start()

    async def stop(self) -> bool:
        await self._cleanup()
        logger.info("停止小红书插件")
        return await super().stop()

    async def _cleanup(self) -> None:
        """Detach all services and cleanup resources."""
        services = [
            self._feed_service,
            self._detail_service, 
            self._comment_service,
        ]
        
        for service in services:
            if service:
                try:
                    await service.detach()
                except Exception as e:
                    logger.warning(f"Service detach failed: {e}")
        
        logger.info("All services detached and cleaned up")

    async def fetch(self) -> Dict[str, Any]:
        """
        Main fetch method that orchestrates data collection using services.
        
        Returns:
            Dictionary containing collected data and metadata
        """
        if not self._feed_service:
            raise RuntimeError("Services not initialized. Call setup() first.")
        
        try:
            # Determine what to collect based on config
            task_type = self.config.extra.get("task_type", "favorites") if self.config.extra else "favorites"
            
            if task_type == "favorites":
                return await self._collect_favorites()
            elif task_type == "search":
                return await self._perform_search()
            elif task_type == "details":
                return await self._collect_details()
            elif task_type == "comments":
                return await self._collect_comments()
            else:
                return await self._collect_favorites()  # Default
                
        except Exception as e:
            logger.error(f"Fetch operation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "plugin_id": self.plugin_id,
                "version": self.version,
            }

    async def _collect_favorites(self) -> Dict[str, Any]:
        """Collect favorite items using the feed service."""
        logger.info("Collecting favorites using feed service")
        
        async def goto_favorites():
            await self.page.goto("https://www.xiaohongshu.com/user/profile/favorites")
            await asyncio.sleep(2)
        
        try:
            items = await self._feed_service.collect(FeedCollectArgs(
                goto_first=goto_favorites,
                extra_config=self.config.extra
            ))
            
            # Convert to dictionaries for JSON serialization
            items_data = [asdict(item) if hasattr(item, '__dataclass_fields__') else item for item in items]
            
            logger.info(f"Successfully collected {len(items_data)} favorite items")
            
            return {
                "success": True,
                "data": items_data,
                "count": len(items_data),
                "plugin_id": self.plugin_id,
                "version": self.version,
                "task_type": "favorites",
            }
            
        except Exception as e:
            logger.error(f"Favorites collection failed: {e}")
            raise

    async def _perform_search(self) -> Dict[str, Any]:
        """Perform search using the search service."""
        if not self._search_service or not self.config.extra:
            raise ValueError("Search service not available or no search keyword provided")
        
        keyword = self.config.extra.get("search_keyword", "")
        if not keyword:
            raise ValueError("No search keyword specified in config.extra.search_keyword")
        
        logger.info(f"Searching for: {keyword}")
        
        try:
            max_batches = self.config.extra.get("max_search_batches", 3)
            delay_ms = self.config.extra.get("search_delay_ms", 800)
            
            results = await self._search_service.search(
                keyword,
                max_batches=max_batches,
                delay_ms=delay_ms
            )
            
            # Convert to dictionaries
            results_data = [asdict(result) if hasattr(result, '__dataclass_fields__') else result for result in results]
            
            logger.info(f"Search found {len(results_data)} results")
            
            return {
                "success": True,
                "data": results_data,
                "count": len(results_data),
                "plugin_id": self.plugin_id,
                "version": self.version,
                "task_type": "search",
                "search_keyword": keyword,
            }
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    async def _collect_details(self) -> Dict[str, Any]:
        """Collect detailed information for specified note IDs."""
        if not self._detail_service or not self.config.extra:
            raise ValueError("Detail service not available or no note IDs provided")
        
        note_ids = self.config.extra.get("note_ids", [])
        if not note_ids:
            raise ValueError("No note IDs specified in config.extra.note_ids")
        
        logger.info(f"Collecting details for {len(note_ids)} notes")
        
        try:
            # Get details in batch
            details = await self._detail_service.get_details_batch(
                note_ids,
                extra_config=self.config.extra
            )
            
            # Filter out None results and convert to dictionaries
            valid_details = [detail for detail in details if detail is not None]
            details_data = [asdict(detail) if hasattr(detail, '__dataclass_fields__') else detail for detail in valid_details]
            
            logger.info(f"Successfully collected {len(details_data)} details out of {len(note_ids)} requested")
            
            return {
                "success": True,
                "data": details_data,
                "count": len(details_data),
                "requested_count": len(note_ids),
                "plugin_id": self.plugin_id,
                "version": self.version,
                "task_type": "details",
            }
            
        except Exception as e:
            logger.error(f"Details collection failed: {e}")
            raise

    async def _collect_comments(self) -> Dict[str, Any]:
        """Collect comments for a specified note."""
        if not self._comment_service or not self.config.extra:
            raise ValueError("Comment service not available or no note ID provided")
        
        note_id = self.config.extra.get("note_id", "")
        if not note_id:
            raise ValueError("No note ID specified in config.extra.note_id")
        
        logger.info(f"Collecting comments for note: {note_id}")
        
        try:
            max_pages = self.config.extra.get("max_comment_pages", 3)
            delay_ms = self.config.extra.get("comment_delay_ms", 500)
            
            comments = await self._comment_service.collect_for_note(
                note_id,
                max_pages=max_pages,
                delay_ms=delay_ms
            )
            
            # Convert to dictionaries
            comments_data = [asdict(comment) if hasattr(comment, '__dataclass_fields__') else comment for comment in comments]
            
            logger.info(f"Successfully collected {len(comments_data)} comments")
            
            return {
                "success": True,
                "data": comments_data,
                "count": len(comments_data),
                "plugin_id": self.plugin_id,
                "version": self.version,
                "task_type": "comments",
                "note_id": note_id,
            }
            
        except Exception as e:
            logger.error(f"Comments collection failed: {e}")
            raise

    def _build_feed_config(self) -> FeedCollectionConfig:
        """Build FeedCollectionConfig from task config."""
        if not self.config or not self.config.extra:
            return FeedCollectionConfig()
        
        extra = self.config.extra
        return FeedCollectionConfig(
            max_items=extra.get("max_items", 1000),
            max_seconds=extra.get("max_seconds", 600),
            max_idle_rounds=extra.get("max_idle_rounds", 2),
            auto_scroll=extra.get("auto_scroll", True),
            scroll_pause_ms=extra.get("scroll_pause_ms", 800),
        )

    def _build_stop_decider(self) -> Optional[Any]:
        """Build a custom stop decider function from config."""
        if not self.config or not self.config.extra:
            return None
        
        extra = self.config.extra
        
        # Check if user wants to stop on specific conditions
        stop_on_tags = extra.get("stop_on_tags", [])
        stop_on_author = extra.get("stop_on_author", "")
        stop_on_title_keywords = extra.get("stop_on_title_keywords", [])
        
        if not (stop_on_tags or stop_on_author or stop_on_title_keywords):
            return None
        
        def custom_stop_decider(page, all_raw, last_raw, all_items, last_batch, elapsed, extra_config, last_view):
            """Custom stop condition based on content."""
            for item in last_batch:
                # Check tags
                if stop_on_tags:
                    item_tags = getattr(item, "tags", []) or []
                    if any(tag.lower() in [t.lower() for t in stop_on_tags] for tag in item_tags):
                        logger.info(f"Found target tag, stopping collection")
                        return True
                
                # Check author
                if stop_on_author:
                    author_info = getattr(item, "author_info", None)
                    if author_info:
                        username = getattr(author_info, "username", "")
                        if stop_on_author.lower() in username.lower():
                            logger.info(f"Found target author, stopping collection")
                            return True
                
                # Check title keywords
                if stop_on_title_keywords:
                    title = getattr(item, "title", "") or ""
                    if any(keyword.lower() in title.lower() for keyword in stop_on_title_keywords):
                        logger.info(f"Found target title keyword, stopping collection")
                        return True
            
            return False
        
        return custom_stop_decider

    # Legacy compatibility methods (delegating to services)
    async def _manual_login(self) -> bool:
        """Legacy method for manual login - now handled by orchestrator."""
        logger.info("Manual login handled by orchestrator, returning success")
        return True

    async def _is_logged_in(self) -> bool:
        """Check if user is logged in by looking for user profile elements."""
        try:
            if not self.page:
                return False
            
            # Check for logged-in indicators
            await self.page.goto("https://www.xiaohongshu.com", wait_until="networkidle")
            
            # Look for user avatar or profile menu
            user_indicators = [
                ".user-avatar",
                ".profile-menu", 
                ".user-info",
                "[data-testid='user-avatar']"
            ]
            
            for selector in user_indicators:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=3000)
                    if element:
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.warning(f"Login check failed: {e}")
            return False


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, config: TaskConfig) -> XiaohongshuV2Plugin:
    p = XiaohongshuV2Plugin()
    p.configure(config)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p