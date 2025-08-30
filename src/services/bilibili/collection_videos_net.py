
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

from src.services.bilibili.models import FavoriteVideoItem
from src.services.collection_common import StopDecider
from src.services.net_consume_helpers import NetConsumeHelper
from src.services.net_service import NetService
from src.services.scroll_helper import ScrollHelper
from src.services.net_collection_loop import (
    NetCollectionState,
    run_network_collection,
)
from src.services.models import AuthorInfo


"""
{
    "code": 0,
    "message": "0",
    "ttl": 1,
    "data": {
        "info": {
            "id": 737546928,
            "fid": 7375469,
            "mid": 475310928,
            "attr": 0,
            "title": "默认收藏夹",
            "cover": "http://i1.hdslb.com/bfs/archive/33ecbf9147f807a43730f6413ffe771aebce29f2.jpg",
            "upper": {
                "mid": 475310928,
                "name": "ASP-SJT",
                "face": "https://i0.hdslb.com/bfs/face/7bad9bb7e35516f4f997b3ea8578d3730b7e5587.jpg",
                "followed": false,
                "vip_type": 1,
                "vip_statue": 0
            },
            "cover_type": 2,
            "cnt_info": {
                "collect": 0,
                "play": 41,
                "thumb_up": 0,
                "share": 0
            },
            "type": 11,
            "intro": "",
            "ctime": 1570167288,
            "mtime": 1663001255,
            "state": 0,
            "fav_state": 0,
            "like_state": 0,
            "media_count": 1332,
            "is_top": false
        },
        "medias": [
            {
                "id": 115011187903147,
                "type": 2,
                "title": "“玩家你好，你的地球Online高级权限已解锁”| 庄周梦蝶的终极隐喻",
                "cover": "http://i1.hdslb.com/bfs/archive/33ecbf9147f807a43730f6413ffe771aebce29f2.jpg",
                "intro": "本期视频主要参考资料：\n《庄子注疏》 [晋] 郭象 注  [唐] 成玄英 疏\n《庄子諵譁》 南怀瑾 著述\n《庄子浅注》 曹础基 著\n《庄子》中华书局版 方勇 译注\n《齐物论》及其影响 陈少明 著\n 梦觉之间：《庄子》思辨录 陈少明 著\n《庄子哲学研究》 杨立华 著 \n《梁冬私房笔记：庄子的心灵自由之路》 梁冬 著\n《控制焦虑》 阿尔伯特·艾利斯 著\n《世界作为参考答案》 刘擎、严飞 著\n《智人之上》 尤瓦尔·赫拉利 著",
                "page": 1,
                "duration": 4810,
                "upper": {
                    "mid": 540073545,
                    "name": "静远的书斋",
                    "face": "https://i0.hdslb.com/bfs/face/0fcb5fa0c41879d5230eaa9690e1f3798b61c615.jpg",
                    "jump_link": ""
                },
                "attr": 0,
                "cnt_info": {
                    "collect": 6113,
                    "play": 47337,
                    "danmaku": 267,
                    "vt": 0,
                    "play_switch": 0,
                    "reply": 0,
                    "view_text_1": "4.7万"
                },
                "link": "bilibili://video/115011187903147",
                "ctime": 1754932107,
                "pubtime": 1754932106,
                "fav_time": 1756429921,
                "bv_id": "BV1dmtUzQE1j",
                "bvid": "BV1dmtUzQE1j",
                "season": null,
                "ogv": null,
                "ugc": {
                    "first_cid": 31632526895
                },
                "media_list_link": "bilibili://music/playlist/playpage/1212857828?page_type=3\u0026oid=115011187903147\u0026otype=2"
            },
"""
class CollectionVideoNetService(NetService[FavoriteVideoItem]):
    """
    Bilibili收藏夹视频抓取服务 - 通过监听网络实现，从 Dom 中提取 Js 对象来获取数据，而非分析标签
    """
    def __init__(self) -> None:
        super().__init__()

    async def attach(self, page: Page) -> None:
        self.state = NetCollectionState[FavoriteVideoItem](page=page, queue=asyncio.Queue())

        # Bind NetRuleBus and start consumer via helper
        self._net_helper = NetConsumeHelper(state=self.state, delegate=self.delegate)
        await self._net_helper.bind(page, [
            (r".*/fav/resource/list.*", "response"),
        ])
        await self._net_helper.start(default_parse_items=self._parse_items_wrapper, payload_ok=lambda _: True)

        await super().attach(page)

    async def detach(self) -> None:
        self.state = None
        await self._net_helper.stop()
        self._net_helper = None
        await super().detach()

    async def invoke(self, extra_params: Dict[str, Any]) -> List[FavoriteVideoItem]:
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
                                   state: Any) -> List[FavoriteVideoItem]:
        collection_info = payload.get("data").get("info")
        medias = payload.get("data").get("medias")
        if not medias or not collection_info:
            return []
        collection_id = collection_info.get("id")
        ret = []
        for item in medias:
            id = str(item.get("id"))
            bvid = item.get("bvid")
            ctime = item.get("ctime")
            pubtime = item.get("pubtime")
            fav_time = item.get("fav_time")
            duration_sec = item.get("duration")
            title = item.get("title")
            intro = item.get("intro")
            cover = item.get("cover")
            creator = item.get("upper")


            ret.append(
                FavoriteVideoItem(
                    id=id,
                    title=title,
                    bvid=bvid,
                    ctime=ctime,
                    pubtime=pubtime,
                    fav_time=fav_time,
                    duration_sec=duration_sec,
                    intro=intro,
                    cover=cover,
                    collection_id=collection_id,
                    creator=AuthorInfo(
                        user_id=creator.get("mid"),
                        username=creator.get("name"),
                        avatar=creator.get("face"),
                        gender=None,
                        is_following=None,
                        is_followed=None,
                        user_type=None,
                    ),
                    raw_data=self._inject_raw_data(item),
                )
            )
        return ret


