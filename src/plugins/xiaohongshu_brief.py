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
from src.services.base import NoteCollectArgs, NetServiceDelegate
from src.services.xiaohongshu.collections.note_net_collection import NoteNetCollectionConfig, NoteNetCollectionState
from src.services.xiaohongshu.models import NoteBriefItem
from src.services.xiaohongshu.note_brief_net import XiaohongshuNoteBriefNetService
from src.utils import wait_until_result
from src.utils.file_util import read_json_with_project_root, write_json_with_project_root

logger = logging.getLogger("plugin.xiaohongshu_brief")

BASE_URL = "https://www.xiaohongshu.com"
LOGIN_URL = f"{BASE_URL}/login"

PLUGIN_ID = "xiaohongshu_brief"
PLUGIN_VERSION = "2.0.0"

class NoteBriefDelegate(NetServiceDelegate[NoteBriefItem]):

    def __init__(self, config: Dict[str, Any]):
        self.storage = InMemoryStorage()
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
            local_data = read_json_with_project_root("data/note-briefs1.json")
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
        write_json_with_project_root(res, "data/note-briefs2.json")

    def get_diff(self) -> DiffResult:
        return self._diff

    async def on_items_collected(self, items: List[NoteBriefItem],
                                 state: Optional[NoteNetCollectionState[NoteBriefItem]]) \
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

    def __init__(self) -> None:
        super().__init__()
        self.plugin_id = PLUGIN_ID
        self.version = PLUGIN_VERSION
        self.description = f"Xiaohongshu note brief info plugin (service-based {PLUGIN_VERSION})"
        
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
                    "plugin_id": self.plugin_id,
                    "version": self.version,
                }
            raise Exception(briefs_res["error"])
                
        except Exception as e:
            logger.error(f"Fetch operation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "plugin_id": self.plugin_id,
                "version": self.version,
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
def create_plugin(ctx: PluginContext, config: TaskConfig) -> XiaohongshuNoteBriefPlugin:
    p = XiaohongshuNoteBriefPlugin()
    p.configure(config)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
