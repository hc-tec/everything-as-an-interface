"""
Xiaohongshu Plugin V2 - Service-based Architecture

This is a thin plugin that orchestrates calls to various Xiaohongshu site services.
The plugin focuses on configuration, coordination, and output formatting,
while delegating specific tasks to specialized services.
"""

import asyncio
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from src.common.plugin import StopDecision
from src.config import get_logger
from src.core.plugin_context import PluginContext
from src.core.task_params import TaskParams
from src.data_sync import SyncParams, InMemoryStorage, PassiveSyncEngine, DiffResult
from src.plugins.base import BasePlugin
from src.plugins.plugin_response import ResponseFactory
from src.plugins.registry import register_plugin
from src.services.net_service import NetServiceDelegate
from src.services.xiaohongshu.models import NoteBriefItem
from src.services.xiaohongshu.note_brief_net import XiaohongshuNoteBriefNetService
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

BASE_URL = "https://www.xiaohongshu.com"
LOGIN_URL = f"{BASE_URL}/login"

PLUGIN_ID = "xiaohongshu_favorites_brief"

class NoteBriefDelegate(NetServiceDelegate[NoteBriefItem]):

    def __init__(self, params: Dict[str, Any]):
        self.storage = InMemoryStorage()
        self.task_params = params

        self.sync_engine = PassiveSyncEngine(storage=self.storage)
        self._stop_decision = StopDecision(should_stop=False, reason=None, details=None)
        self._diff = DiffResult(added=[], updated=[], deleted=[])

        self.sync_engine.parse_params(params)

    async def load_storage_from_data(self, data):
        try:
            local_data = data
            if local_data["count"] != 0:
                await self.storage.upsert_many(local_data["data"])
                logger.debug(f"Loaded data, Data count: {local_data['count']}")
        except Exception as e:
            logger.warning(f"Failed to load data: {e}")

    def get_storage_data(self):
        items = list(self.storage.get_items())
        return items

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

    def make_stop_decision(self, loop_count, extra_params, page, state, new_batch, idle_rounds, elapsed) -> StopDecision:
        return self._stop_decision

class XiaohongshuNoteBriefPlugin(BasePlugin):

    @dataclass
    class Params:
        storage_data: str = "{}"

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
        self.plugin_params: Optional[XiaohongshuNoteBriefPlugin.Params] = None
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
            self._note_brief_delegate = NoteBriefDelegate(self.task_params.extra)

            # Set Delegates to Services
            self._note_brief_net_service.set_delegate(self._note_brief_delegate)

            # Attach all services to the page
            await self._note_brief_net_service.attach(self.page)

            self.plugin_params = ParamsHelper.build_params(XiaohongshuNoteBriefPlugin.Params, self.task_params.extra)

            # Set custom stop conditions if specified
            self._note_brief_net_service.set_stop_decider(self._note_brief_delegate.make_stop_decision)

            logger.info(f"{self._note_brief_net_service.__class__.__name__} service initialized and attached")

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

        self._note_brief_net_service.set_params(self.task_params.extra)

        try:
            await self._note_brief_delegate.load_storage_from_data(self.task_params.extra.get("storage_data", {}))
            briefs_res = await self._collect_briefs()
            if briefs_res["success"]:
                diff = self._note_brief_delegate.get_diff()
                logger.info(f"diff: {diff.stats()}")
                full_data = self._note_brief_delegate.get_storage_data()
                return self._response.ok(data={
                    "data": full_data,
                    "count": len(full_data),
                    "added": {
                        "data": diff.added,
                        "count": len(diff.added),
                    },
                    "updated": {
                        "data": diff.updated,
                        "count": len(diff.updated),
                    },
                })
            raise Exception(briefs_res["error"])
                
        except Exception as e:
            logger.error(f"Fetch operation failed: {e}")
            return self._response.fail(error=str(e))

    async def _collect_briefs(self) -> Dict[str, Any]:
        if not self._note_brief_net_service:
            raise RuntimeError("Services not initialized. Call setup() first.")
        """Collect favorite items using the note_net service."""
        logger.info("Collecting favorites using note_brief_net service")

        await self.page.click('.user, .side-bar-component')
        await asyncio.sleep(1)
        await self.page.click(".sub-tab-list:nth-child(2)")
        items = await self._note_brief_net_service.invoke(self.task_params.extra)
        # Convert to dictionaries for JSON serialization
        items_data = [asdict(item) for item in items]
        logger.info(f"Successfully collected {len(items_data)} results")
        return self._response.ok(data=items_data)


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, params: TaskParams) -> XiaohongshuNoteBriefPlugin:
    p = XiaohongshuNoteBriefPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
