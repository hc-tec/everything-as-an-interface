"""
Xiaohongshu Plugin V2 - Service-based Architecture

This is a thin plugin that orchestrates calls to various Xiaohongshu site services.
The plugin focuses on configuration, coordination, and output formatting,
while delegating specific tasks to specialized services.
"""

import asyncio
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from playwright.async_api import expect

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
from src.services.xiaohongshu.note_collection_brief_net import XiaohongshuNoteCollectionBriefNetService
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

BASE_URL = "https://www.xiaohongshu.com"
LOGIN_URL = f"{BASE_URL}/login"

PLUGIN_ID = "xiaohongshu_favorites_brief"

def extract_id_from_href(href: str) -> str | None:
    """
    从一个 href 字符串中提取 ID.
    例如: 从 "/board/651d0e09000000001700e4ef?source=..." 提取 "651d0e09000000001700e4ef"
    """
    # 使用正则表达式匹配 /board/ 和 ? 之间的部分
    match = re.search(r"/board/([^?]+)", href)
    if match:
        return match.group(1)
    return None

class NoteBriefDelegate(NetServiceDelegate[NoteBriefItem]):

    def __init__(self, params: Dict[str, Any]):
        self.storage = InMemoryStorage()
        self.task_params = params

        self.sync_engine = PassiveSyncEngine(storage=self.storage)
        self._stop_decision = StopDecision(should_stop=False, reason=None, details=None)
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
        """Custom stop decision based on PassiveSyncEngine analysis.

        The PassiveSyncEngine tracks:
        - Consecutive known items (items already in storage)
        - Consecutive no-change batches (batches with no new/updated data)
        - Total new items in session

        Returns the decision from PassiveSyncEngine, which may stop collection when:
        - Too many consecutive known items detected
        - Too many batches with no changes
        - Maximum new items reached
        """
        return self._stop_decision

class XiaohongshuNoteBriefPlugin(BasePlugin):

    @dataclass
    class Params:
        storage_data: str = "{}"
        collection_id: Optional[str] = None

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
        self._note_collection_brief_net_service: Optional[XiaohongshuNoteCollectionBriefNetService] = None

        # Service Delegate Instances
        # 为每个 service 创建独立的 delegate，避免数据混淆
        # 当访问特定收藏夹时，导航过程会经过默认收藏夹页面，如果共用 delegate 会导致数据混在一起
        self._note_brief_delegate: Optional[NoteBriefDelegate] = None  # 用于默认收藏夹
        self._note_collection_brief_delegate: Optional[NoteBriefDelegate] = None  # 用于特定收藏夹


    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            # Initialize services
            self._note_brief_net_service = XiaohongshuNoteBriefNetService()
            self._note_collection_brief_net_service = XiaohongshuNoteCollectionBriefNetService()

            # Initialize Delegates - 为每个 service 创建独立的 delegate 实例
            self._note_brief_delegate = NoteBriefDelegate(self.task_params.extra)
            self._note_collection_brief_delegate = NoteBriefDelegate(self.task_params.extra)

            # Set Delegates to Services - 使用独立的 delegate
            self._note_brief_net_service.set_delegate(self._note_brief_delegate)
            self._note_collection_brief_net_service.set_delegate(self._note_collection_brief_delegate)

            self.plugin_params = ParamsHelper.build_params(XiaohongshuNoteBriefPlugin.Params, self.task_params.extra)

            # 根据是否有 collection_id 来决定 attach 哪个 service
            # 这样可以避免在导航过程中触发不需要的网络监听
            if self.plugin_params.collection_id:
                # 只 attach 特定收藏夹的 service
                await self._note_collection_brief_net_service.attach(self.page)
                self._note_collection_brief_net_service.set_stop_decider(self._note_collection_brief_delegate.make_stop_decision)
                logger.info(f"{self._note_collection_brief_net_service.__class__.__name__} service initialized and attached")
            else:
                # 只 attach 默认收藏夹的 service
                await self._note_brief_net_service.attach(self.page)
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
            self._note_collection_brief_net_service
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

        # 根据是否有 collection_id 来决定使用哪个 delegate
        active_delegate = self._note_collection_brief_delegate if self.plugin_params.collection_id else self._note_brief_delegate

        # 只为需要的 service 设置参数
        if self.plugin_params.collection_id:
            self._note_collection_brief_net_service.set_params(self.task_params.extra)
        else:
            self._note_brief_net_service.set_params(self.task_params.extra)

        try:
            # 加载存储数据到对应的 delegate
            if not isinstance(self.plugin_params.storage_data, list):
                await active_delegate.load_storage_from_data(json.loads(self.plugin_params.storage_data))
            briefs_res = await self._collect_briefs()
            if briefs_res["success"]:
                # 从对应的 delegate 获取数据
                diff = active_delegate.get_diff()
                logger.info(f"diff: {diff.stats()}")
                full_data = active_delegate.get_storage_data()
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

    async def find_collection_position_and_click(self, collection_to_find):
        # =================================================================
        # 第一步: 提取所有 ID 形成列表
        # =================================================================
        container_locator = self.page.locator(".tab-content-item:nth-child(2) .board-wrapper")
        # 确保这个容器元素是可见的，这是一个好习惯
        await expect(container_locator).to_be_visible()
        # 获取该容器下所有 a 标签的 href 属性
        # a[href*='/board/'] 是一个CSS选择器，优化了定位，只选择 href 包含 '/board/' 的 a 标签
        # 为了复用，我们先定义好所有链接的定位器
        links_locator = container_locator.locator("a[href*='/board/']")
        # 获取所有 href 属性
        all_hrefs = await links_locator.evaluate_all(
            "elements => elements.map(el => el.getAttribute('href'))"
        )
        # 遍历所有 href，提取 ID，并过滤掉提取失败的 None 值
        id_list = [extract_id_from_href(href) for href in all_hrefs if href]

        # =================================================================
        # 第二步: 查找指定 ID 的位置
        # =================================================================
        try:
            # 使用 list.index() 方法查找索引。注意：列表索引是从 0 开始的。
            position = id_list.index(collection_to_find)
            # 使用 .nth(position) 来精确定位到列表中的第 position 个元素
            target_link_locator = links_locator.nth(position)
            # 执行点击操作
            await target_link_locator.click()
            # 点击后通常会发生页面跳转，建议等待页面加载完成
            await self.page.wait_for_load_state("load")
            return True
        except ValueError:
            # 如果 .index() 找不到元素，会抛出 ValueError 异常
            return False

    async def _collect_briefs(self) -> Dict[str, Any]:
        if not self._note_brief_net_service or not self._note_collection_brief_net_service:
            raise RuntimeError("Services not initialized. Call setup() first.")
        """Collect favorite items using the note_net service."""
        logger.info("Collecting favorites using note_brief_net service")
        if self.plugin_params.collection_id:
            await self.page.click('.user, .side-bar-component')
            await asyncio.sleep(1)
            await self.page.click(".sub-tab-list:nth-child(2)")
            await asyncio.sleep(0.5)
            await self.page.click(".tertiary.left.reds-tabs-list .reds-tab-item:nth-child(2)")
            await asyncio.sleep(1)

            success = await self.find_collection_position_and_click(self.plugin_params.collection_id)
            if not success:
                raise Exception("Cannot find collection")
            items = await self._note_collection_brief_net_service.invoke(self.task_params.extra)
        else:
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
