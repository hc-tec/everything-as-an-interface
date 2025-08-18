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
from src.data_sync import SyncConfig, InMemoryStorage, PassiveSyncEngine, DiffResult
from src.plugins.base import BasePlugin
from src.plugins.registry import register_plugin
from src.services.base import NoteCollectArgs, NetServiceDelegate, ServiceConfig
from src.services.xiaohongshu.collections.note_net_collection import NoteNetCollectionState
from src.services.xiaohongshu.models import NoteBriefItem
from src.services.xiaohongshu.note_brief_net import XiaohongshuNoteBriefNetService
from src.utils.file_util import read_json_with_project_root, write_json_with_project_root

logger = logging.getLogger("plugin.xiaohongshu_brief")

BASE_URL = "https://www.xiaohongshu.com"
LOGIN_URL = f"{BASE_URL}/login"

PLUGIN_ID = "xiaohongshu_brief"

class NoteBriefDelegate(NetServiceDelegate[NoteBriefItem]):

    def __init__(self, config: Dict[str, Any]):
        self.storage = InMemoryStorage()
        self.config = config
        self.sync_engine = PassiveSyncEngine(
            storage=self.storage,
            config=SyncConfig(
                identity_key="id",
                deletion_policy=config.get("deletion_policy", "soft"),
                stop_after_consecutive_known=config.get("stop_after_consecutive_known", 5),
                stop_after_no_change_batches=config.get("stop_after_no_change_batches", 2),
                max_new_items=config.get("stop_max_items", 10),
                fingerprint_fields=["id", "title"],
            )
        )
        self._stop_decision = StopDecision(should_stop=False, reason=None, details=None)
        self._diff = DiffResult(added=[], updated=[], deleted=[])

    async def load_storage_from_file(self):
        try:
            local_data = read_json_with_project_root(self.config.get("storage_file", "data/note-briefs.json"))
            if local_data["count"] != 0:
                await self.storage.upsert_many(local_data["data"])
                logger.debug(f"Loaded note-briefs.json, Data count: {local_data['count']}")
        except Exception as e:
            logger.warning(f"Failed to load note-briefs.json: {e}")

    def save_storage_to_file(self):
        items = list(self.storage.get_items())
        res = {
            "success": True,
            "count": len(items),
            "data": items,
        }
        write_json_with_project_root(res, self.config.get("storage_file", "data/note-briefs.json"))

    def get_diff(self) -> DiffResult:
        return self._diff

    async def on_items_collected(self, items: List[NoteBriefItem],
                                 consume_count: int,
                                 extra: Dict[str, Any],
                                 state: Any) \
            -> List[NoteBriefItem]:
        diff, decision = await self.sync_engine.process_batch([asdict(item) for item in items])
        logger.debug("added: %s", len(diff.added))
        logger.debug("updated: %s", len(diff.updated))
        logger.debug("deleted: %s", len(diff.deleted))
        logger.debug("should_stop: %s, %s", decision.should_stop, decision.reason)

        self._stop_decision = decision
        self._diff.added.extend(diff.added)
        self._diff.updated.extend(diff.updated)
        self._diff.deleted.extend(diff.deleted)
        return items

    def make_stop_decision(self, loop_count: int, extra: Dict[str, Any], page, all_raw_responses,
                           last_raw_response, all_parsed_items, last_batch_parsed_items,
                           elapsed_seconds, last_response_view) -> StopDecision:
        return self._stop_decision

class XiaohongshuNoteBriefPlugin(BasePlugin):
    """
    Xiaohongshu Plugin V2 - Thin orchestration layer using site services.
    
    This plugin demonstrates the service-based architecture where:
    - Plugin handles configuration and orchestration
    - Services handle site-specific logic and data collection
    - Plugin formats and returns results
    """

    # 每个插件必须定义唯一的插件ID
    PLUGIN_ID: str = PLUGIN_ID
    # 插件名称
    PLUGIN_NAME: str = __name__
    # 插件版本
    PLUGIN_VERSION: str = "2.0.0"
    # 插件描述
    PLUGIN_DESCRIPTION: str = f"Xiaohongshu note brief info plugin (service-based v{PLUGIN_VERSION})"
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
        self._note_brief_net_service: Optional[XiaohongshuNoteBriefNetService] = None

        # Service Delegate Instances
        # 通过建立新的 Delegate 实现类，避免让 Plugin 直接作为 Delegate，这样在碰到多个 Service 都需要实现 Delegate 时可以避免重写冲突
        self._note_brief_delegate: Optional[NoteBriefDelegate] = None


    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            # Initialize services
            self._note_brief_net_service = XiaohongshuNoteBriefNetService()

            # Initialize Delegates
            self._note_brief_delegate = NoteBriefDelegate(self.config.extra)
            await self._note_brief_delegate.load_storage_from_file()

            # Set Delegates to Services
            self._note_brief_net_service.set_delegate(self._note_brief_delegate)

            # Attach all services to the page
            await self._note_brief_net_service.attach(self.page)

            # Configure note_net service based on task config
            note_net_config = self._build_note_net_config()
            self._note_brief_net_service.configure(note_net_config)

            # Set custom stop conditions if specified
            self._note_brief_net_service.set_stop_decider(self._note_brief_delegate.make_stop_decision)

            logger.info("XiaohongshuNoteBriefPlugin service initialized and attached")

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
            self._note_brief_net_service,
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
            briefs_res = await self._collect_briefs()
            if briefs_res["success"]:
                self._note_brief_delegate.save_storage_to_file()
                diff = self._note_brief_delegate.get_diff()
                logger.info(f"diff: {diff.stats()}")
                return {
                    "success": True,
                    "data": diff.added,
                    "count": len(diff.added),
                    "plugin_id": self.PLUGIN_ID,
                    "version": self.PLUGIN_VERSION,
                }
            raise Exception(briefs_res["error"])
                
        except Exception as e:
            logger.error(f"Fetch operation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "plugin_id": self.PLUGIN_ID,
                "version": self.PLUGIN_VERSION,
            }

    async def _collect_briefs(self) -> Dict[str, Any]:
        if not self._note_brief_net_service:
            raise RuntimeError("Services not initialized. Call setup() first.")
        """Collect favorite items using the note_net service."""
        logger.info("Collecting favorites using note_brief_net service")

        async def goto_favorites():
            await self.page.click('.user, .side-bar-component')
            await asyncio.sleep(1)
            await self.page.click(".sub-tab-list:nth-child(2)")

        try:
            items = await self._note_brief_net_service.collect(NoteCollectArgs(
                goto_first=goto_favorites,
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

        def custom_stop_decider(page, all_raw, last_raw, all_items, last_batch, elapsed, extra_config, last_view) \
                -> StopDecision:
            return StopDecision(should_stop=False, reason=None, details=None)
        
        return custom_stop_decider


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, config: TaskConfig) -> XiaohongshuNoteBriefPlugin:
    p = XiaohongshuNoteBriefPlugin()
    p.configure(config)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
