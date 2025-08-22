"""
Xiaohongshu Plugin V2 - Service-based Architecture

This is a thin plugin that orchestrates calls to various Xiaohongshu site services.
The plugin focuses on configuration, coordination, and output formatting,
while delegating specific tasks to specialized services.
"""

import asyncio
import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

from src.common.plugin import StopDecision
from src.core.plugin_context import PluginContext
from src.core.task_config import TaskConfig
from src.plugins.base import BasePlugin
from src.plugins.registry import register_plugin
from src.services.base_service import ServiceConfig
from src.services.xiaohongshu.common import NoteCollectArgs
from src.services.xiaohongshu.note_search_net import XiaohongshuNoteSearchNetService

logger = logging.getLogger("plugin.xiaohongshu_search")

BASE_URL = "https://www.xiaohongshu.com"
LOGIN_URL = f"{BASE_URL}/login"

PLUGIN_ID = "xiaohongshu_search"


class XiaohongshuNoteSearchPlugin(BasePlugin):
    """
    Xiaohongshu Plugin V2 - Thin orchestration layer using site services.
    
    This plugin demonstrates the service-based architecture where:
    - Plugin handles configuration and orchestration
    - Services handle site-specific logic and data collection
    - Plugin formats and returns results
    """

    # 平台/登录配置（供 BasePlugin 通用登录逻辑使用）
    LOGIN_URL = "https://www.xiaohongshu.com/login"
    PLATFORM_ID = "xiaohongshu"
    LOGGED_IN_SELECTORS = [
        ".reds-img-box",
    ]

    # 每个插件必须定义唯一的插件ID
    PLUGIN_ID: str = PLUGIN_ID
    # 插件名称
    PLUGIN_NAME: str = __name__
    # 插件版本
    PLUGIN_VERSION: str = "2.0.0"
    # 插件描述
    PLUGIN_DESCRIPTION: str = f"Xiaohongshu note search plugin (service-based v{PLUGIN_VERSION})"
    # 插件作者
    PLUGIN_AUTHOR: str = ""

    def __init__(self) -> None:
        super().__init__()

        # Initialize services (will be attached during setup)
        self._note_search_net_service: Optional[XiaohongshuNoteSearchNetService] = None


    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            # Initialize services
            self._note_search_net_service = XiaohongshuNoteSearchNetService()

            # Attach all services to the page
            await self._note_search_net_service.attach(self.page)

            # Configure note_net service based on task config
            note_net_config = self._build_note_net_config()
            self._note_search_net_service.configure(note_net_config)

            logger.info("XiaohongshuNoteSearchPlugin service initialized and attached")

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
            self._note_search_net_service,
        ]
        
        for service in services:
            if service:
                try:
                    await service.detach()
                except Exception as e:
                    logger.warning(f"Service detach failed: {e}")
        
        logger.info("All services detached and cleaned up")

    def validate_config(self) -> Dict[str, Any]:
        if self.config.extra.get("search_words") is None:
            return { "valid": False, "errors": ["You should provide search_words in TaskConfig"] }
        return { "valid": True, "errors": [] }

    async def fetch(self) -> Dict[str, Any]:
        """
        Main fetch method that orchestrates data collection using services.
        
        Returns:
            Dictionary containing collected data and metadata
        """

        await self._ensure_logged_in()

        try:
            briefs_res = await self._collect_briefs()
            if briefs_res["success"]:
                return {
                    "success": True,
                    "data": briefs_res["data"],
                    "count": len(briefs_res["data"]),
                    "plugin_id": PLUGIN_ID,
                    "version": self.PLUGIN_VERSION,
                }
            raise Exception(briefs_res["error"])
                
        except Exception as e:
            logger.error(f"Fetch operation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "plugin_id": PLUGIN_ID,
                "version": self.PLUGIN_VERSION,
            }

    async def _collect_briefs(self) -> Dict[str, Any]:
        if not self._note_search_net_service:
            raise RuntimeError("Services not initialized. Call setup() first.")
        """Collect favorite items using the note_net service."""
        logger.info("Collecting favorites using note_brief_net service")

        async def to_search_page():
            search_words = self.config.extra.get("search_words")
            url = f"https://www.xiaohongshu.com/search_result?keyword={search_words}&source=web_search_result_notes"
            await self.page.goto(url, wait_until="load")
            await asyncio.sleep(1)

        try:
            items = await self._note_search_net_service.collect(NoteCollectArgs(
                goto_first=to_search_page,
                extra_config=self.config.extra
            ))

            # Convert to dictionaries for JSON serialization
            items_data = [asdict(item) for item in items]

            logger.info(f"Successfully collected {len(items_data)} favorite items")

            return {
                "success": True,
                "data": items_data,
                "count": len(items_data),
                "task_type": "briefs",
            }

        except Exception as e:
            logger.error(f"Briefs collection failed: {e}")
            return {
                "success": False,
                "data": None,
                "count": 0,
                "task_type": "briefs",
                "error": str(e),
            }

    def _build_note_net_config(self) -> ServiceConfig:
        """Build ServiceConfig from task config."""
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

        def custom_stop_decider(loop_count, extra_config, page, state, new_batch, elapsed) -> StopDecision:
            return StopDecision(should_stop=False, reason=None, details=None)
        
        return custom_stop_decider


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, config: TaskConfig) -> XiaohongshuNoteSearchPlugin:
    p = XiaohongshuNoteSearchPlugin()
    p.configure(config)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
