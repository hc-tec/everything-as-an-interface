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

from src.common.plugin import StopDecision
from src.core.plugin_context import PluginContext
from src.core.task_config import TaskConfig
from src.plugins.base import BasePlugin
from src.plugins.registry import register_plugin
from src.services.base import NoteCollectArgs, T, ServiceConfig
from src.services.xiaohongshu.collections.note_net_collection import NoteNetCollectionConfig, NoteNetCollectionState
from src.services.xiaohongshu.homepage_feed_net import XiaohongshuHomepageFeedNetService

logger = logging.getLogger("plugin.xiaohongshu")

PLUGIN_ID = "xiaohongshu"
PLUGIN_VERSION = "2.0.0"


class XiaohongshuPlugin(BasePlugin):
    """
    Xiaohongshu Plugin V2 - Thin orchestration layer using site services.
    
    This plugin demonstrates the service-based architecture where:
    - Plugin handles configuration and orchestration
    - Services handle site-specific logic and data collection
    - Plugin formats and returns results
    """

    # BasePlugin 通用登录会读取这些可选的类属性
    LOGIN_URL = "https://www.xiaohongshu.com/login"
    PLATFORM_ID = "xiaohongshu"
    LOGGED_IN_SELECTORS = [
        ".reds-img-box",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.plugin_id = PLUGIN_ID
        self.version = PLUGIN_VERSION
        self.description = f"Xiaohongshu automation plugin (service-based v{PLUGIN_VERSION})"
        
        # Initialize services (will be attached during setup)
        self._homepage_feed_net_service: Optional[XiaohongshuHomepageFeedNetService] = None


    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            # Initialize services
            self._homepage_feed_net_service = XiaohongshuHomepageFeedNetService()


            # Attach all services to the page
            await self._homepage_feed_net_service.attach(self.page)

            # Configure note_net service based on task config
            note_net_config = self._build_note_net_config()
            self._homepage_feed_net_service.configure(note_net_config)

            stop_decider = self._build_stop_decider()
            if stop_decider:
                self._homepage_feed_net_service.set_stop_decider(stop_decider)

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
            self._homepage_feed_net_service,
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
        try:
            # Ensure user is logged in before proceeding
            await self._ensure_logged_in()
            
            # Collect note briefs first
            briefs = await self._collect_note_briefs()
            
            if not briefs:
                logger.warning("No note briefs collected")
                return {
                    "success": True,
                    "data": [],
                    "count": 0,
                    "plugin_id": self.plugin_id,
                    "version": self.version,
                }
            
            return {
                "success": True,
                "data": briefs,
                "count": len(briefs),
                "plugin_id": self.plugin_id,
                "version": self.version,
            }
                
        except Exception as e:
            logger.error(f"Fetch operation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "plugin_id": self.plugin_id,
                "version": self.version,
            }

    async def _collect_note_briefs(self) -> List[Dict[str, Any]]:
        """Collect note briefs from homepage feed."""
        if not self._homepage_feed_net_service:
            raise RuntimeError("Services not initialized. Call setup() first.")
        
        logger.info("Starting note brief collection")
        
        try:
            # Navigate to homepage first  
            await self.page.goto("https://www.xiaohongshu.com", wait_until="load")
            await asyncio.sleep(2)  # Allow page to settle
            
            # Get notes using the service
            notes = await self._homepage_feed_net_service.collect(
                NoteCollectArgs(extra_config=self.config.extra)
            )
            
            # Filter out None results and convert to dictionaries
            valid_notes = [note for note in notes if note is not None]
            notes_data = [asdict(note) for note in valid_notes]
            
            logger.info(f"Collected {len(notes_data)} note briefs")
            return notes_data
            
        except Exception as e:
            logger.error(f"Note brief collection failed: {e}")
            raise

    def _build_note_net_config(self) -> ServiceConfig:
        """Build NoteNetCollectionConfig from task config."""
        if not self.config or not self.config.extra:
            return ServiceConfig()
        
        extra = self.config.extra
        return ServiceConfig(
            max_items=extra.get("max_items", 1000),
            max_seconds=extra.get("max_seconds", 600),
            max_idle_rounds=extra.get("max_idle_rounds", 2),
            auto_scroll=extra.get("auto_scroll", True),
            scroll_pause_ms=extra.get("scroll_pause_ms", 800),
        )

    def _build_stop_decider(self) -> Optional[Any]:
        """Build custom stop decider function if specified in config."""
        # In the future, we could parse config to build different stop conditions
        # For now, return a basic implementation
        def custom_stop_decider(page, all_raw, last_raw, all_items, last_batch, elapsed, extra_config, last_view) \
                -> StopDecision:
            return StopDecision(should_stop=False, reason=None, details=None)
        
        return custom_stop_decider


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, config: TaskConfig) -> XiaohongshuPlugin:
    p = XiaohongshuPlugin()
    p.configure(config)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
