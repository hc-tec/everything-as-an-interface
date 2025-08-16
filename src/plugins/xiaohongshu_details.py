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
from src.data_sync import DiffResult
from src.plugins.base import BasePlugin
from src.plugins.registry import register_plugin
from src.services.base import NoteCollectArgs, T
from src.services.xiaohongshu.collections.note_net_collection import NoteNetCollectionConfig, NoteNetCollectionState
from src.services.xiaohongshu.models import NoteAccessInfo, NoteDetailsItem
from src.services.xiaohongshu.note_explore_page_net import XiaohongshuNoteExplorePageNetService
from src.utils import wait_until_result
from src.utils.file_util import read_json_with_project_root, write_json_with_project_root

logger = logging.getLogger("plugin.xiaohongshu_detail")

BASE_URL = "https://www.xiaohongshu.com"
LOGIN_URL = f"{BASE_URL}/login"

PLUGIN_ID = "xiaohongshu_detail"
PLUGIN_VERSION = "2.0.0"


class XiaohongshuNoteDetailPlugin(BasePlugin):
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
        self.description = f"Xiaohongshu automation plugin (service-based v{PLUGIN_VERSION})"
        
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

            # Configure note_net service based on task config
            note_net_config = self._build_note_net_config()
            self._note_explore_net_service.configure(note_net_config)

            stop_decider = self._build_stop_decider()
            if stop_decider:
                self._note_explore_net_service.set_stop_decider(stop_decider)

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

        try:
            diff_file_path = self.config.extra.get("diff_file")
            diff_data = read_json_with_project_root(diff_file_path)
            if diff_data.get("count") > 0:
                diff = diff_data["data"]
                return await self._collect_details(diff)
            raise Exception(diff_data.get("error"))
                
        except Exception as e:
            logger.error(f"Fetch operation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "plugin_id": self.plugin_id,
                "version": self.version,
            }

    async def navigate_to_note_explore_page(self, loop_count: int,
                                            extra: Dict[str, Any]):
        access_info: NoteAccessInfo = extra.get("access_info")[loop_count - 1]
        note_explore_page = f"https://www.xiaohongshu.com/explore/{access_info.id}?xsec_token={access_info.xsec_token}&xsec_source=pc_feed"
        await self.page.goto(note_explore_page, wait_until="load")
        await asyncio.sleep(10)

    @staticmethod
    async def stop_to_note_explore_page_when_all_collected(
            loop_count: int, extra: Dict[str, Any], page, all_raw_responses,
            last_raw_response, all_parsed_items, last_batch_parsed_items,
            elapsed_seconds, last_response_view):
        is_all_collected = loop_count >= len(extra.get("access_info"))
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
        # 利用此回调，我们可以让网页跳转到笔记详情页
        self._note_explore_net_service.set_stop_decider(self.stop_to_note_explore_page_when_all_collected)
        self._note_explore_net_service.set_delegate_on_items_collected(self.on_items_collected)
        # 小红书进入笔记详情，必须得有两个参数，一个是 id，另一个是 xsec_token
        note_access_info = [
            NoteAccessInfo(id=item["id"], xsec_token=item["xsec_token"])
            for item in added_briefs_items
        ]

        try:
            # Get details in batch
            details = await self._note_explore_net_service.collect(NoteCollectArgs(
                    goto_first=None,
                    on_tick_start=self.navigate_to_note_explore_page,
                    extra_config={
                        "access_info": note_access_info,
                        **self.config.extra
                    }
                )
            )
            
            # Filter out None results and convert to dictionaries
            valid_details = [detail for detail in details if detail is not None]
            details_data = [asdict(detail) for detail in valid_details]
            
            logger.info(f"Successfully collected {len(details_data)} details out of {len(added_briefs_items)} requested")

            logger.info(f"Collect failed notes, total: {len(self._access_failed_notes)}")
            write_json_with_project_root({
                "success": False,
                "data": [asdict(access_info) for access_info in self._access_failed_notes],
                "count": len(self._access_failed_notes),
                "plugin_id": self.plugin_id,
                "version": self.version,
            }, self.config.extra.get("failed_file"))
            
            return {
                "success": True,
                "data": details_data,
                "count": len(details_data),
                "requested_count": len(added_briefs_items),
                "plugin_id": self.plugin_id,
                "version": self.version,
            }
            
        except Exception as e:
            logger.error(f"Details collection failed: {e}")
            raise

    def _build_note_net_config(self) -> NoteNetCollectionConfig:
        """Build NoteNetCollectionConfig from task config."""
        if not self.config or not self.config.extra:
            return NoteNetCollectionConfig()
        
        extra = self.config.extra
        return NoteNetCollectionConfig(
            max_items=extra.get("max_items", 1000),
            max_seconds=extra.get("max_seconds", 600),
            max_idle_rounds=extra.get("max_idle_rounds", 2),
            auto_scroll=extra.get("auto_scroll", True),
            scroll_pause_ms=extra.get("scroll_pause_ms", 800),
        )

    def _build_stop_decider(self) -> Optional[Any]:

        def custom_stop_decider(page, all_raw, last_raw, all_items, last_batch, elapsed, extra_config, last_view) \
                -> StopDecision:
            return StopDecision(should_stop=False, reason=None, details=None)
        
        return custom_stop_decider

    async def _try_cookie_login(self) -> bool:
        if not self.page:
            return False
        cookie_ids: List[str] = list(self.config.get("cookie_ids", []))
        if self.account_manager and cookie_ids:
            try:
                merged = self.account_manager.merge_cookies(cookie_ids)
                if merged:
                    await self.page.context.add_cookies(merged)
                    await self.page.goto(BASE_URL)
                    await asyncio.sleep(2)
                    if await self._is_logged_in():
                        logger.info("使用配置的 Cookie 登录成功")
                        return True
                    logger.warning("提供的 Cookie 未生效")
            except Exception as exc:  # noqa: BLE001
                logger.error(f"注入 Cookie 失败: {exc}")
        return False

    async def _manual_login(self) -> bool:
        if not self.page:
            return False
        try:
            await self.page.goto(LOGIN_URL)
            await asyncio.sleep(1)
            logger.info("请在浏览器中手动登录小红书，系统会自动检测登录状态…")
            async def check_login():
                if await self._is_logged_in():
                    logger.info("检测到登录成功")
                    try:
                        cookies = await self.page.context.cookies()
                        if cookies and self.account_manager:
                            cookie_id = self.account_manager.add_cookies(
                                "xiaohongshu", cookies, name="登录获取"
                            )
                            if cookie_id:
                                logger.info(f"Cookie 已保存: {cookie_id}")
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(f"获取或保存 Cookie 失败: {exc}")
                    return True
                return None
            await wait_until_result(check_login, timeout=120000)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error(f"手动登录过程异常: {exc}")
            return False

    async def _is_logged_in(self) -> bool:
        """Check if user is logged in by looking for user profile elements."""
        try:
            if not self.page:
                return False
            
            # Look for user avatar or profile menu
            user_indicators = [
                '.reds-img-box',
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
def create_plugin(ctx: PluginContext, config: TaskConfig) -> XiaohongshuNoteDetailPlugin:
    p = XiaohongshuNoteDetailPlugin()
    p.configure(config)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
