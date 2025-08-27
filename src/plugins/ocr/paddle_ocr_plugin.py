
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
from src.services.ocr.paddle_ocr_service import PaddleOCRService, paddle_ocr_service
from src.utils.params_helper import ParamsHelper

logger = get_logger(__name__)

PLUGIN_ID = "paddle_ocr"


class PaddleOcrPlugin(BasePlugin):

    # 每个插件必须定义唯一的插件ID
    PLUGIN_ID: str = PLUGIN_ID
    # 插件名称
    PLUGIN_NAME: str = __name__
    # 插件版本
    PLUGIN_VERSION: str = "1.0.0"
    # 插件描述
    PLUGIN_DESCRIPTION: str = f"Paddle ocr plugin (v{PLUGIN_VERSION})"
    # 插件作者
    PLUGIN_AUTHOR: str = ""

    def __init__(self) -> None:
        super().__init__()
        # Initialize services (will be attached during setup)
        self._service: Optional[PaddleOCRService] = paddle_ocr_service

    async def start(self) -> bool:
        try:
            # Attach all services to the page
            await self._service.attach(self.page)

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
        try:
            result = self._service.invoke(self.task_params.extra)
            return {
                "success": True,
                "data": result,
                "plugin_id": PLUGIN_ID,
                "version": self.PLUGIN_VERSION,
            }
        except Exception as e:
            logger.error(f"Fetch operation failed: {e}", exc_info=e)
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "plugin_id": PLUGIN_ID,
                "version": self.PLUGIN_VERSION,
            }


@register_plugin(PLUGIN_ID)
def create_plugin(ctx: PluginContext, params: TaskParams) -> PaddleOcrPlugin:
    p = PaddleOcrPlugin()
    p.inject_task_params(params)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
