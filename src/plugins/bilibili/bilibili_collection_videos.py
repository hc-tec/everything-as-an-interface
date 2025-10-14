
import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, List

from playwright.async_api import ElementHandle

from src.common.plugin import StopDecision
from src.config import get_logger
from src.core.plugin_context import PluginContext
from src.core.task_params import TaskParams
from src.data_sync import InMemoryStorage, PassiveSyncEngine, DiffResult
from src.plugins.base import BasePlugin
from src.plugins.plugin_response import ResponseFactory
from src.plugins.registry import register_plugin
from src.services.bilibili.collection_videos_net import CollectionVideoNetService
from src.services.bilibili.models import FavoriteVideoItem
from src.services.collection_common import CollectionState
from src.services.net_service import NetServiceDelegate
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

BASE_URL = "https://www.bilibili.com"
LOGIN_URL = f"{BASE_URL}"

PLUGIN_ID = "bilibili_collection_videos"

class BriefUpdateDelegate(NetServiceDelegate[FavoriteVideoItem]):

    def __init__(self, params: Dict[str, Any]):
        self.storage = InMemoryStorage()
        self.task_params = params

        self.sync_engine = PassiveSyncEngine(storage=self.storage)
        self.stop_decision = StopDecision(should_stop=False, reason=None, details=None)
        self._diff = DiffResult(added=[], updated=[], deleted=[])

        self.sync_engine.parse_params(params)

    async def load_storage_from_data(self, data: Dict[str, Any]):
        try:
            await self.storage.upsert_many(data)
            logger.debug(f"Loaded data, Data count: {len(data)}")
        except Exception as e:
            logger.error(f"Failed to load data: {e}")

    def get_storage_data(self):
        items = list(self.storage.get_items())
        return items

    def get_diff(self) -> DiffResult:
        return self._diff

    async def on_items_collected(self, items: List[FavoriteVideoItem],
                                 consume_count: int,
                                 extra: Dict[str, Any],
                                 state: Any) \
            -> List[FavoriteVideoItem]:
        diff, decision = await self.sync_engine.process_batch([asdict(item) for item in items])
        logger.debug("added: %s", len(diff.added))
        logger.debug("updated: %s", len(diff.updated))
        logger.debug("deleted: %s", len(diff.deleted))
        logger.debug("should_stop: %s, %s", decision.should_stop, decision.reason)

        self.stop_decision = decision
        self._diff.added.extend(diff.added)
        self._diff.updated.extend(diff.updated)
        self._diff.deleted.extend(diff.deleted)
        return items

    def make_stop_decision(self, loop_count, extra_params, page, state, new_batch, idle_rounds, elapsed) -> StopDecision:
        return self.stop_decision



class BilibiliCollectionVideosPlugin(BasePlugin):

    @dataclass
    class Params:
        collection_id: Optional[str] # 传入需要获取的收藏夹ID列表
        storage_data: Optional[str] = field(default_factory=lambda : [])
        user_id: Optional[str] = None
        total_page: Optional[int] = None
        fingerprint_fields: Optional[list[str]] = None

    # 平台/登录配置（供 BasePlugin 通用登录逻辑使用）
    LOGIN_URL = LOGIN_URL
    PLATFORM_ID = "bilibili"
    LOGGED_IN_SELECTORS = [
        ".bili-avatar-img",
        ".bili-avatar",
        ".header-entry-mini",
    ]

    # 每个插件必须定义唯一的插件ID
    PLUGIN_ID: str = PLUGIN_ID
    # 插件名称
    PLUGIN_NAME: str = __name__
    # 插件版本
    PLUGIN_VERSION: str = "1.0.0"
    # 插件描述
    PLUGIN_DESCRIPTION: str = f"Bilibili Collection Videos plugin (service-based v{PLUGIN_VERSION})"
    # 插件作者
    PLUGIN_AUTHOR: str = ""

    def __init__(self) -> None:
        super().__init__()
        self.plugin_params: Optional[BilibiliCollectionVideosPlugin.Params] = None
        # Initialize services (will be attached during setup)
        self._service: Optional[CollectionVideoNetService] = None
        self._update_delegate: Optional[BriefUpdateDelegate] = None

    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            await self._dont_open_new_page()
            self._service = CollectionVideoNetService()
            # Attach all services to the page
            await self._service.attach(self.page)

            # Initialize Delegates
            self._update_delegate = BriefUpdateDelegate(self.task_params.extra)

            # Set Delegates to Services
            self._service.set_delegate_on_items_collected(self._update_delegate.on_items_collected)

            self.plugin_params = ParamsHelper.build_params(BilibiliCollectionVideosPlugin.Params, self.task_params.extra)

            logger.info(f"{self._service.__class__.__name__} service initialized and attached")

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
        if self._service:
            try:
                await self._service.detach()
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
            if not isinstance(self.plugin_params.storage_data, list):
                await self._update_delegate.load_storage_from_data(json.loads(self.plugin_params.storage_data))
            return await self._collect()
        except Exception as e:
            logger.error(f"Fetch operation failed: {e}")
            return self._response.fail(error=str(e))

    async def _make_stop_decision(self,
                                  loop_count,
                                  extra_params,
                                  page,
                                  state: CollectionState,
                                  *args, **kwargs):
        if self._update_delegate.stop_decision.should_stop:
            return self._update_delegate.stop_decision
        if loop_count >= self.plugin_params.total_page:
            return StopDecision(should_stop=True, reason="Reach max collection count")
        return StopDecision(should_stop=False, reason="Don't reach max collection count")

    async def _get_total_page_num(self):
        logger.debug("尝试获取当前收藏夹的总页数")
        try:
            btn = await self.page.wait_for_selector("div.vui_pagenation--btns button:nth-last-of-type(2)", timeout=2000)
            total_page_num = int(await btn.text_content())
            self.plugin_params.total_page = total_page_num
        except Exception as e:
            self.plugin_params.total_page = 1

    async def _click_to_next_page(self,
                                  loop_count: int,
                                  extra_params: Dict[str, Any],
                                  state: CollectionState):
        logger.debug("进入下一页")
        try:
            input_ = await self.page.wait_for_selector(".vui_pagenation-go input", timeout=200)
            await input_.type(str(loop_count+1))
            await input_.press("Enter")
        except Exception as e:
            pass

    async def _collect(self) -> Dict[str, Any]:
        if self.plugin_params.user_id is None:
            # 跳转到自己的个人空间中
            avatar = await self.page.wait_for_selector(".header-entry-mini", timeout=5000)
            await avatar.click()
            await asyncio.sleep(1)
            await self.page.wait_for_load_state("load")
            url = self.page.url
            match = re.search(r"https?://space\.bilibili\.com/(\d+)", url)
            if match:
                self.plugin_params.user_id = match.group(1)
            else:
                raise RuntimeError("User ID not found. Check url correctly.")
        else:
            # 直接跳转到个人空间中
            pass

        user_id = self.plugin_params.user_id
        collection_id = self.plugin_params.collection_id
        url = f"https://space.bilibili.com/{user_id}/favlist?fid={collection_id}&ftype=create"
        await self.page.goto(url, wait_until="load")

        await self._get_total_page_num()

        self._service.set_stop_decider(self._make_stop_decision)
        self._service.set_delegate_on_loop_item_end(self._click_to_next_page)
        items = await self._service.invoke(self.task_params.extra)

        # Convert to dictionaries for JSON serialization
        items_data = [asdict(item) for item in items]

        logger.info(f"Successfully collected {len(items_data)} results")

        diff = self._update_delegate.get_diff()
        logger.info(f"diff: {diff.stats()}")
        full_data = self._update_delegate.get_storage_data()
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


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, params: TaskParams) -> BilibiliCollectionVideosPlugin:
    p = BilibiliCollectionVideosPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
