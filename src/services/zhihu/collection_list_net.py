
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.collection_common import StopDecider
from src.services.net_consume_helpers import NetConsumeHelper
from src.services.net_service import NetService
from src.services.scroll_helper import ScrollHelper
from src.services.net_collection_loop import (
    NetCollectionState,
    run_network_collection,
)
from src.services.models import CollectionItem, AuthorInfo


class CollectionListNetService(NetService[CollectionItem]):
    """
    知乎收藏夹列表抓取服务 - 通过监听网络实现，从 Dom 中提取 Js 对象来获取笔记数据，而非分析标签
    """
    def __init__(self) -> None:
        super().__init__()

    async def attach(self, page: Page) -> None:
        self.page = page
        self.state = NetCollectionState[CollectionItem](page=page, queue=asyncio.Queue())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*/people/.*/collections.*", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper, payload_ok=lambda _: True)

        await super().attach(page)

    async def invoke(self, extra_params: Dict[str, Any]) -> List[CollectionItem]:
        if not self.page or not self.state:
            raise RuntimeError("Service not attached to a Page")

        self._net_helper.set_extra(extra_params)

        pause = self._service_params.scroll_pause_ms
        on_scroll = ScrollHelper.build_on_scroll(self.page, service_params=self._service_params,
                                                 pause_ms=pause, extra=extra_params)

        items = await run_network_collection(
            self.state,
            self._service_params,
            extra_params=extra_params or {},
            on_scroll=on_scroll,
            delegate=self.loop_delegate,
        )
        return items

    async def _parse_items_wrapper(self,
                                   payload: Dict[str, Any],
                                   consume_count: int,
                                   extra: Dict[str, Any],
                                   state: Any) -> List[CollectionItem]:
        collection_list = payload.get("data")
        if not collection_list:
            return []
        ret = []
        for item in collection_list:
            id = str(item.get("id"))
            title = item.get("title")
            description = item.get("description")
            link = item.get("url")
            item_count = item.get("item_count")
            is_default = item.get("is_default")
            creator = item.get("creator")
            created_time = item.get("created_time")
            updated_time = item.get("updated_time")

            ret.append(
                CollectionItem(
                    id=id,
                    title=title,
                    description=description,
                    link=link,
                    item_count=item_count,
                    is_default=is_default,
                    creator=AuthorInfo(
                        user_id=creator.get("id"),
                        username=creator.get("name"),
                        avatar=creator.get("avatar_url"),
                        gender=creator.get("gender"),
                        is_following=creator.get("is_following"),
                        is_followed=creator.get("is_followed"),
                        user_type=creator.get("user_type"),
                    ),
                    created_time=created_time,
                    updated_time=updated_time,
                    raw_data=self._inject_raw_data(item),
                )
            )
        return ret


