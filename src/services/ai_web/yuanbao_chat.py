from __future__ import annotations

import asyncio
from src.config import get_logger
from typing import Any, Dict, List, Optional

from glom import glom
from playwright.async_api import Page

from src.services.net_collection_loop import (
    NetCollectionState,
    run_network_collection,
)
from src.services.net_consume_helpers import NetConsumeHelper
from src.services.net_service import NetService
from src.services.scroll_helper import ScrollHelper
from src.services.ai_web.models import Conversation, Message

logger = get_logger(__name__)

class YuanbaoChatNetService(NetService[Conversation]):
    """
    元宝网页端AI服务 - 通过监听网络实现，而非解析 Dom
    """
    def __init__(self) -> None:
        super().__init__()

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = NetCollectionState[Conversation](page=page, queue=asyncio.Queue())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*/conversation/.*/detail", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper, payload_ok=lambda x:True)

        await super().attach(page)

    async def invoke(self, extra_params: Dict[str, Any]) -> List[Conversation]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        pause = self._service_params.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(self.page, service_params=self._service_params, pause_ms=pause, extra=extra_params)

        items = await run_network_collection(
            self.state,
            self._service_params,
            extra_params=extra_params or {},
            on_scroll=on_scroll,
            network_timeout=60,  # 一分钟超时
            delegate=self.loop_delegate,
        )
        return items

    async def _parse_items_wrapper(self,
                                   payload: Dict[str, Any],
                                   consume_count: int,
                                   extra: Dict[str, Any],
                                   state: Any) -> List[Conversation]:
        convs = payload.get("convs", [])
        messages = []
        for conv in convs:
            if conv.get("chatInputType", "text") == "text":
                try:
                    text = glom(conv, "speechesV2.0.content.0.msg")
                except Exception:
                    text = None
                tokens_used = glom(conv, "speechesV2.0.extra.usage.completion_tokens")
                msg = Message(
                    msg_id=conv.get("subConversationId"),
                    sender="model" if conv.get("speaker") == "ai" else "user",
                    content=text,
                    timestamp=conv.get("createTime"),
                    tokens_used=tokens_used,
                    status=conv.get("status")
                )
                messages.append(msg)

        last_user_message = None
        last_model_message = None

        for msg in messages:
            if msg.sender == "model":
                last_model_message = msg.content
            elif msg.sender == "user":
                last_user_message = msg.content
            if last_model_message and last_user_message:
                break

        return [
            Conversation(
            model_name=payload.get("chatModelId"),
            messages=messages,
            conversation_id=payload.get("id"),
            user_id=payload.get("userId"),
            first_replied_timestamp=payload.get("firstRepliedAt"),
            last_replied_timestamp=payload.get("lastRepliedAt"),
            last_user_message=last_user_message,
            last_model_message=last_model_message,
            conversation_length=payload.get("maxIndex"),
            status="",
            total_tokens_used=0,
            context_window_size="",
            session_title=payload.get("title"),
            raw_data=self._inject_raw_data(payload),
        )]
