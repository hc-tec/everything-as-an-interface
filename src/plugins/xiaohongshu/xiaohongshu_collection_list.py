"""
Xiaohongshu Details Plugin V2 - Service-based Architecture

This plugin orchestrates calls to Xiaohongshu services to collect detailed note information.
"""

import asyncio
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from src.common.plugin import StopDecision
from src.config import get_logger
from src.core.plugin_context import PluginContext
from src.core.task_params import TaskParams
from src.plugins.base import BasePlugin
from src.plugins.plugin_response import ResponseFactory
from src.plugins.registry import register_plugin
from src.services.xiaohongshu.collection_list_net import CollectionListNetService
from src.services.xiaohongshu.models import NoteAccessInfo, NoteDetailsItem
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

BASE_URL = "https://www.xiaohongshu.com"
LOGIN_URL = f"{BASE_URL}/login"

PLUGIN_ID = "xiaohongshu_collection_list"


class XiaohongshuCollectionListPlugin(BasePlugin):

    # 每个插件必须定义唯一的插件ID
    PLUGIN_ID: str = PLUGIN_ID
    # 插件名称
    PLUGIN_NAME: str = __name__
    # 插件版本
    PLUGIN_VERSION: str = "2.0.0"
    # 插件描述
    PLUGIN_DESCRIPTION: str = f"Xiaohongshu automation plugin (service-based v{PLUGIN_VERSION})"
    # 插件作者
    PLUGIN_AUTHOR: str = ""

    # 平台/登录配置（供 BasePlugin 通用登录逻辑使用）
    LOGIN_URL = "https://www.xiaohongshu.com/login"
    PLATFORM_ID = "xiaohongshu"
    LOGGED_IN_SELECTORS = [
        ".reds-img-box",
    ]

    def __init__(self) -> None:
        super().__init__()
        # Initialize services (will be attached during setup)
        self._service: Optional[CollectionListNetService] = None
        self._access_failed_notes: List[NoteAccessInfo] = []

    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            # Initialize services
            self._service = CollectionListNetService()

            # Attach all services to the page
            await self._service.attach(self.page)


            logger.info("XiaohongshuCollectionListPlugin service initialized and attached")

        except Exception as e:
            logger.error(f"Service setup failed: {e}")
            raise
        logger.info("启动插件")
        return await super().start()

    async def stop(self) -> bool:
        await self._cleanup()
        logger.info("停止插件")
        return await super().stop()

    async def _cleanup(self) -> None:
        """Detach all services and cleanup resources."""
        services = [
            self._service,
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

        await self._ensure_logged_in()
        self._service.set_params(self.task_params.extra)

        try:
            # brief_data = self.plugin_params.brief_data
            # brief_data = json.loads(brief_data)
            # if brief_data.get("count") > 0:
            #     diff = brief_data["data"]
            #     return await self._collect(diff)
            return await self._collect()

        except Exception as e:
            logger.error(f"Fetch operation failed: {e}", exc_info=e)
            return self._response.fail(error=str(e))

    @staticmethod
    async def stop_to_note_explore_page_when_all_collected(
            loop_count,
            extra_params,
            page,
            state,
            new_batch,
            idle_rounds,
            elapsed):
        is_all_collected = loop_count >= 1
        if is_all_collected:
            return StopDecision(should_stop=True, reason="All collections collected", details=None)
        return StopDecision(should_stop=False, reason=None, details=None)

    # 通过此函数将访问失败的笔记ID记下来
    async def on_items_collected(self, items: List[NoteDetailsItem],
                                 consume_count: int,
                                 extra: Dict[str, Any],
                                 state: Any) -> List[NoteDetailsItem]:
        if not items:
            access_info = extra.get("access_info")[consume_count - 1]
            self._access_failed_notes.append(access_info)
        return items

    async def _collect(self) -> Dict[str, Any]:
        """Collect detailed information for specified note IDs."""
        if not self._service:
            raise RuntimeError("Services not initialized. Call setup() first.")

        self._service.set_stop_decider(self.stop_to_note_explore_page_when_all_collected)

        await self.page.click('.user, .side-bar-component')
        await asyncio.sleep(1)
        await self.page.click(".sub-tab-list:nth-child(2)")
        await asyncio.sleep(1)
        await self.page.click(".tertiary.left.reds-tabs-list .reds-tab-item:nth-child(2)")

        items = await self._service.invoke(self.task_params.extra)

        # Convert to dictionaries for JSON serialization
        items_data = [asdict(item) for item in items]

        logger.info(f"Successfully collected {len(items_data)} results")

        return self._response.ok(data=items_data)


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, params: TaskParams) -> XiaohongshuCollectionListPlugin:
    p = XiaohongshuCollectionListPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
