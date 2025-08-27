
import asyncio
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.common.plugin import StopDecision
from src.config import get_logger
from src.core.plugin_context import PluginContext
from src.core.task_params import TaskParams
from src.plugins.base import BasePlugin
from src.plugins.registry import register_plugin
from src.services.ai_web.yuanbao_chat import YuanbaoChatNetService
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

BASE_URL = "https://yuanbao.tencent.com/chat/naQivTmsDa/"
LOGIN_URL = f"{BASE_URL}/login"

PLUGIN_ID = "yuanbao_chat"


class YuanbaoChatPlugin(BasePlugin):

    @dataclass
    class Params:
        ask_question: str
        conversation_id: Optional[str] = None

    # 平台/登录配置（供 BasePlugin 通用登录逻辑使用）
    LOGIN_URL = "https://yuanbao.tencent.com/chat/naQivTmsDa/"
    PLATFORM_ID = "yuanbao"
    LOGGED_IN_SELECTORS = [
        ".yb-recent-conv-list__item",
    ]

    # 每个插件必须定义唯一的插件ID
    PLUGIN_ID: str = PLUGIN_ID
    # 插件名称
    PLUGIN_NAME: str = __name__
    # 插件版本
    PLUGIN_VERSION: str = "1.0.0"
    # 插件描述
    PLUGIN_DESCRIPTION: str = f"Ai Yuanbao in Web (service-based v{PLUGIN_VERSION})"
    # 插件作者
    PLUGIN_AUTHOR: str = ""

    def __init__(self) -> None:
        super().__init__()
        self.plugin_params: Optional[YuanbaoChatPlugin.Params] = None
        # Initialize services (will be attached during setup)
        self._chat_service: Optional[YuanbaoChatNetService] = None

    # -----------------------------
    # 生命周期
    # -----------------------------
    async def start(self) -> bool:
        try:
            # Initialize services
            self._chat_service = YuanbaoChatNetService()

            # Attach all services to the page
            await self._chat_service.attach(self.page)

            self.plugin_params = ParamsHelper.build_params(YuanbaoChatPlugin.Params, self.task_params.extra)

            logger.info("YuanbaoChatPlugin service initialized and attached")

        except Exception as e:
            logger.error(f"Service setup failed: {e}")
            raise
        logger.info("启动AI元宝网页端插件")
        return await super().start()

    async def stop(self) -> bool:
        await self._cleanup()
        logger.info("停止AI元宝网页端插件")
        return await super().stop()

    async def _cleanup(self) -> None:
        """Detach all services and cleanup resources."""
        services = [
            self._chat_service,
        ]

        for service in services:
            if service:
                try:
                    await service.detach()
                except Exception as e:
                    logger.warning(f"Service detach failed: {e}")

        logger.info("All services detached and cleaned up")

    def validate_params(self) -> Dict[str, Any]:
        if self.plugin_params.ask_question is None:
            return {"valid": False, "errors": ["You should provide ask_question in TaskParams"]}
        return {"valid": True, "errors": []}

    async def fetch(self) -> Dict[str, Any]:
        """
        Main fetch method that orchestrates data collection using services.

        Returns:
            Dictionary containing collected data and metadata
        """

        await self._ensure_logged_in()

        self._chat_service.set_params(self.task_params.extra)

        try:
            res = await self._chat_with_ai()
            if res["success"]:
                return {
                    "success": True,
                    "data": res["data"],
                    "count": len(res["data"]),
                    "plugin_id": PLUGIN_ID,
                    "version": self.PLUGIN_VERSION,
                }
            raise Exception(res["error"])

        except Exception as e:
            logger.error(f"Fetch operation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "plugin_id": PLUGIN_ID,
                "version": self.PLUGIN_VERSION,
            }
    @staticmethod
    async def custom_stop_decider_three_times(loop_count, extra_params, page, state, new_batch, idle_rounds, elapsed) -> StopDecision:
        if loop_count == 3:
            return StopDecision(should_stop=True, reason="send over when executing three times", details=None)
        else:
            return StopDecision(should_stop=False, reason=None, details=None)

    @staticmethod
    async def custom_stop_decider_twice(loop_count, extra_params, page, state, new_batch, idle_rounds,
                                              elapsed) -> StopDecision:
        if loop_count == 2:
            return StopDecision(should_stop=True, reason="send over when executing twice", details=None)
        else:
            return StopDecision(should_stop=False, reason=None, details=None)

    @staticmethod
    async def custom_stop_decider_once(loop_count, extra_params, page, state, new_batch, idle_rounds,
                                       elapsed) -> StopDecision:
        if loop_count == 1:
            return StopDecision(should_stop=True, reason="only execute once", details=None)
        else:
            return StopDecision(should_stop=False, reason=None, details=None)

    async def _chat_with_ai(self) -> Dict[str, Any]:
        if not self._chat_service:
            raise RuntimeError("Services not initialized. Call setup() first.")
        """Collect favorite items using the note_net service."""
        logger.info("Collecting favorites using note_brief_net service")

        conversation_id = self.plugin_params.conversation_id
        if conversation_id:
            self._chat_service.set_stop_decider(self.custom_stop_decider_three_times)
            await self.page.goto(f"https://yuanbao.tencent.com/chat/naQivTmsDa/{conversation_id}", wait_until="load")
        else:
            self._chat_service.set_stop_decider(self.custom_stop_decider_twice)
            await self.page.goto("https://yuanbao.tencent.com/chat/naQivTmsDa", wait_until="load")

        await asyncio.sleep(1)
        locator = self.page.locator('[class^="style__text-area__start___"]')
        await locator.type(self.task_params.extra["ask_question"])
        await asyncio.sleep(0.5)
        sender = await self.page.query_selector("#yuanbao-send-btn")
        await sender.click()
        try:
            items = await self._chat_service.invoke(self.task_params.extra)

            await self.page.reload(wait_until="load")

            self._chat_service.set_stop_decider(self.custom_stop_decider_once)
            self._chat_service.state.clear()
            items = await self._chat_service.invoke(self.task_params.extra)

            # Convert to dictionaries for JSON serialization
            items_data = [asdict(item) for item in items]

            logger.info(f"Successfully chat")

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


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, params: TaskParams) -> YuanbaoChatPlugin:
    p = YuanbaoChatPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
