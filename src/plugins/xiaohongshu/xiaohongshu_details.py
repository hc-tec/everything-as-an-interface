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
from src.plugins.registry import register_plugin
from src.services.xiaohongshu.models import NoteAccessInfo, NoteDetailsItem
from src.services.xiaohongshu.note_explore_page_net import XiaohongshuNoteExplorePageNetService
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

BASE_URL = "https://www.xiaohongshu.com"
LOGIN_URL = f"{BASE_URL}/login"

PLUGIN_ID = "xiaohongshu_details"


class XiaohongshuNoteDetailPlugin(BasePlugin):

    @dataclass
    class Params:
        brief_data: str = "{}"
        wait_time_sec: int = 10

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
        self.plugin_params: Optional[XiaohongshuNoteDetailPlugin.Params] = None
        # Initialize services (will be attached during setup)
        self._note_explore_net_service: Optional[XiaohongshuNoteExplorePageNetService] = None

        self._access_failed_notes: List[NoteAccessInfo] = []


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
        logger.info("启动小红书详情插件")
        return await super().start()

    async def stop(self) -> bool:
        await self._cleanup()
        logger.info("停止小红书详情插件")
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
            Dictionary containing collected data and metadata
        """

        await self._ensure_logged_in()
        self._note_explore_net_service.set_params(self.task_params.extra)

        try:
            brief_data = self.plugin_params.brief_data
            brief_data = json.loads(brief_data)
            if brief_data.get("count") > 0:
                diff = brief_data["data"]
                return await self._collect_details(diff)
            raise Exception(brief_data.get("error"))
                
        except Exception as e:
            logger.error(f"Fetch operation failed: {e}", exc_info=e)
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "plugin_id": PLUGIN_ID,
                "version": self.PLUGIN_VERSION,
            }

    async def navigate_to_note_explore_page(self,
                                            loop_count: int,
                                            extra: Dict[str, Any],
                                            state: Any):
        # 利用此回调，我们可以让网页跳转到笔记详情页
        access_info: NoteAccessInfo = extra.get("access_info")[loop_count - 1]
        note_explore_page = f"https://www.xiaohongshu.com/explore/{access_info.id}?xsec_token={access_info.xsec_token}&xsec_source=pc_feed"
        await self.page.goto(note_explore_page, wait_until="load")
        await asyncio.sleep(self.plugin_params.wait_time_sec)

    @staticmethod
    async def stop_to_note_explore_page_when_all_collected(
            loop_count,
            extra_params,
            page,
            state,
            new_batch,
            elapsed):
        is_all_collected = loop_count >= len(extra_params.get("access_info"))
        if is_all_collected:
            return StopDecision(should_stop=True, reason="All notes collected", details=None)
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

    async def _collect_details(self, added: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Collect detailed information for specified note IDs."""
        if not self._note_explore_net_service:
            raise RuntimeError("Services not initialized. Call setup() first.")

        added_briefs_items = added
        if added_briefs_items is None or len(added_briefs_items) == 0:
            raise ValueError("No added notes found")
        
        logger.info(f"Collecting details for {len(added_briefs_items)} notes")
        self._note_explore_net_service.set_stop_decider(self.stop_to_note_explore_page_when_all_collected)
        self._note_explore_net_service.set_delegate_on_items_collected(self.on_items_collected)
        # 小红书进入笔记详情，必须得有两个参数，一个是 id，另一个是 xsec_token
        note_access_info = [
            NoteAccessInfo(id=item["id"], xsec_token=item["xsec_token"])
            for item in added_briefs_items
        ]

        try:
            self._note_explore_net_service.set_delegate_on_loop_item_start(self.navigate_to_note_explore_page)
            # Get details in batch
            details = await self._note_explore_net_service.invoke(extra_params={
                "access_info": note_access_info,
                **self.task_params.extra
            })
            
            # Filter out None results and convert to dictionaries
            valid_details = [detail for detail in details if detail is not None]
            details_data = [asdict(detail) for detail in valid_details]
            
            logger.info(f"Successfully collected {len(details_data)} details out of {len(added_briefs_items)} requested")

            logger.info(f"Collect failed notes, total: {len(self._access_failed_notes)}")
            
            return {
                "success": True,
                "data": details_data,
                "count": len(details_data),
                "failed_notes": {
                    "data": [asdict(access_info) for access_info in self._access_failed_notes],
                    "count": len(self._access_failed_notes),
                },
                "requested_count": len(added_briefs_items),
                "plugin_id": PLUGIN_ID,
                "version": self.PLUGIN_VERSION,
            }
            
        except Exception as e:
            logger.error(f"Details collection failed: {e}", exc_info=e)
            raise e


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, params: TaskParams) -> XiaohongshuNoteDetailPlugin:
    p = XiaohongshuNoteDetailPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
