"""
Xiaohongshu Details Plugin V2 - Service-based Architecture

This plugin orchestrates calls to Xiaohongshu services to collect detailed note information.
Now supports single note detail retrieval.
"""

import asyncio
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from src.config import get_logger
from src.core.plugin_context import PluginContext
from src.core.task_params import TaskParams
from src.plugins.base import BasePlugin
from src.plugins.plugin_response import ResponseFactory
from src.plugins.registry import register_plugin
from src.services.xiaohongshu.models import NoteDetailsItem
from src.services.xiaohongshu.note_explore_page_net import XiaohongshuNoteExplorePageNetService
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

BASE_URL = "https://www.xiaohongshu.com"
LOGIN_URL = f"{BASE_URL}/login"

PLUGIN_ID = "xiaohongshu_details"


class XiaohongshuNoteDetailPlugin(BasePlugin):

    @dataclass
    class Params:
        note_id: str = ""
        xsec_token: str = ""
        wait_time_sec: int = 3

    # 每个插件必须定义唯一的插件ID
    PLUGIN_ID: str = PLUGIN_ID
    # 插件名称
    PLUGIN_NAME: str = __name__
    # 插件版本
    PLUGIN_VERSION: str = "3.0.0"
    # 插件描述
    PLUGIN_DESCRIPTION: str = f"Xiaohongshu single note detail plugin (service-based v{PLUGIN_VERSION})"
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
        self.plugin_params: Optional[XiaohongshuNoteDetailPlugin.Params] = None
        # Initialize services (will be attached during setup)
        self._note_explore_net_service: Optional[XiaohongshuNoteExplorePageNetService] = None


    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            # Initialize services
            self._note_explore_net_service = XiaohongshuNoteExplorePageNetService()

            # Attach all services to the page
            await self._note_explore_net_service.attach(self.page)

            self.plugin_params = ParamsHelper.build_params(XiaohongshuNoteDetailPlugin.Params, self.task_params.extra)

            logger.info("XiaohongshuNoteDetailPlugin service initialized and attached")

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
            self._note_explore_net_service,
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
            Dictionary containing single note detail data
        """

        await self._ensure_logged_in()
        self._note_explore_net_service.set_params(self.task_params.extra)

        try:
            # Validate input parameters
            if not self.plugin_params.note_id:
                raise ValueError("note_id is required")
            if not self.plugin_params.xsec_token:
                raise ValueError("xsec_token is required")

            # Collect single note detail
            return await self._collect_single_detail()

        except Exception as e:
            logger.error(f"Fetch operation failed: {e}", exc_info=e)
            return self._response.fail(error=str(e))

    async def _collect_single_detail(self) -> Dict[str, Any]:
        """Collect detailed information for a single specified note."""
        if not self._note_explore_net_service:
            raise RuntimeError("Services not initialized. Call setup() first.")

        note_id = self.plugin_params.note_id
        xsec_token = self.plugin_params.xsec_token

        logger.info(f"Collecting detail for note: {note_id}")

        # Navigate to note explore page
        note_explore_page = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_feed"
        logger.info(f"Navigating to: {note_explore_page}")

        await self.page.goto(note_explore_page, wait_until="load")
        await asyncio.sleep(self.plugin_params.wait_time_sec)

        # Invoke service to collect detail (expects single item in response)
        details = await self._note_explore_net_service.invoke(extra_params={
            **self.task_params.extra
        })

        # Check if we got a result
        if not details or len(details) == 0:
            logger.warning(f"Failed to collect detail for note: {note_id}")
            return self._response.fail(error=f"No detail data returned for note {note_id}")

        # Get the first (and should be only) detail
        detail = details[0]
        detail_data = asdict(detail)

        logger.info(f"Successfully collected detail for note: {note_id}")

        return self._response.ok(data=detail_data)


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, params: TaskParams) -> XiaohongshuNoteDetailPlugin:
    p = XiaohongshuNoteDetailPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
