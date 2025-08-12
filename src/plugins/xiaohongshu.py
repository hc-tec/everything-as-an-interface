import asyncio
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from playwright.async_api import ElementHandle

from src.core.task_config import TaskConfig

from ..plugins.base import BasePlugin
from ..utils.async_utils import wait_until_result
from ..utils.net_rules import net_rule_match, bind_network_rules, ResponseView, RuleContext
from ..utils import Mp4DownloadSession
from .registry import register_plugin
from ..core.plugin_context import PluginContext
from src.services.xiaohongshu.collections.note_net_collection import (
    FeedCollectionConfig,
    FeedCollectionState,
    run_network_collection,
    record_response as feed_record_response,
)

logger = logging.getLogger("plugin.xiaohongshu")


# -----------------------------
# 常量与选择器
# -----------------------------
BASE_URL = "https://www.xiaohongshu.com"
LOGIN_URL = f"{BASE_URL}/login"

@dataclass
class AuthorInfo:
    user_id: str
    username: str
    avatar: str

@dataclass
class NoteStatistics:
    like_num: str      # 点赞数量
    collect_num: str   # 收藏数量
    chat_num: str      # 评论数量

@dataclass
class VideoInfo:
    duration_sec: int
    src: str

@dataclass
class FavoriteItem:
    id: str
    title: str
    author_info: AuthorInfo
    tags: List[str]
    date: str
    ip_zh: str
    comment_num: str
    statistic: NoteStatistics
    images: Optional[list[str]]
    video: Optional[VideoInfo]
    timestamp: str


class XiaohongshuPlugin(BasePlugin):
    """小红书插件：实现收藏夹监听等功能"""

    # 插件元信息
    PLUGIN_ID = "xiaohongshu"
    PLUGIN_NAME = "小红书"
    PLUGIN_DESCRIPTION = "小红书自动化接口，支持收藏夹监听等功能"
    PLUGIN_VERSION = "0.2.0"
    PLUGIN_AUTHOR = "Everything As An Interface"

    def __init__(self) -> None:
        super().__init__()
        # 页面注入：使用 self.page
        self.last_favorites: List[Dict[str, Any]] = []
        self._unbind_net_rules: Optional[Callable[[], None]] = None
        self._net_note_items: List[FavoriteItem] = []
        self._video_session: Optional[Mp4DownloadSession] = None
        self.ctx: Optional[PluginContext] = None
        self._net_note_event: Optional[asyncio.Event] = None
        # 用户可插入的停止判定函数与网络原始响应记录
        self._stop_decider: Optional[Callable[[Any, List[Any], Optional[Any], List[FavoriteItem], List[FavoriteItem], float, Dict[str, Any], Optional[ResponseView]], Any]] = None
        self._net_responses: List[Any] = []
        self._net_last_response: Optional[Any] = None
        self._net_last_response_view: Optional[ResponseView] = None

    # -----------------------------
    # 生命周期
    # -----------------------------
    def start(self) -> bool:
        logger.info("启动小红书插件")
        return super().start()

    def stop(self) -> bool:
        asyncio.create_task(self._cleanup())
        logger.info("停止小红书插件")
        return super().stop()

    async def _cleanup(self) -> None:
        if self._unbind_net_rules and self.page:
            try:
                self._unbind_net_rules()
            except Exception:
                pass
            self._unbind_net_rules = None

    # -----------------------------
    # 公共流程入口
    # -----------------------------
    async def fetch(self) -> Dict[str, Any]:
        await self._ensure_page_ready()
        try:
            if not await self._ensure_logged_in():
                return {
                    "success": False,
                    "message": "登录失败，请检查网络连接或重试",
                    "need_relogin": True,
                }
            # await asyncio.sleep(1000)
            favorites = await self._get_favorites()
            if not favorites:
                return {
                    "success": False,
                    "message": "获取收藏夹内容失败，可能是DOM结构变化或登录状态失效",
                    "favorites": [],
                }

            new_items = favorites
            self.last_favorites = favorites

            return {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "total_favorites": len(favorites),
                "new_favorites": len(new_items),
                "favorites": favorites,
                "new_items": new_items,
                "input": self.get_input(),
            }
        except Exception as exc:  # noqa: BLE001
            logger.error(f"获取数据失败: {exc}")
            return {"success": False, "message": str(exc)}

    # -----------------------------
    # 配置校验
    # -----------------------------
    def validate_config(self, config: TaskConfig) -> Dict[str, Any]:
        errors: List[str] = []

        if "interval" in config and (not isinstance(config["interval"], int) or config["interval"] < 60):
            errors.append("轮询间隔必须是大于等于60的整数（秒）")

        if "headless" in config and not isinstance(config["headless"], bool):
            errors.append("headless 必须是布尔值")

        if "cookie_ids" in config and not isinstance(config["cookie_ids"], list):
            errors.append("cookie_ids 必须是字符串ID列表")

        if "favorites_url" in config and not isinstance(config["favorites_url"], str):
            errors.append("favorites_url 必须是字符串")

        if "user_id" in config and not isinstance(config["user_id"], str):
            errors.append("user_id 必须是字符串")

        return {"valid": len(errors) == 0, "errors": errors}

    # -----------------------------
    # 内部工具方法（使用注入的 Page）
    # -----------------------------
    async def _ensure_page_ready(self) -> None:
        if not self.page:
            raise RuntimeError("插件未注入 Page，请先调用 set_page(page)")
        # 初始化视频下载会话与网络规则绑定
        if not self._video_session:
            self._video_session = Mp4DownloadSession(
                output_dir=self.config.extra.get("video_output_dir", "videos"),
                proactive_on_first_seen=True,
            )
        # 若通过注册工厂注入了 ctx，则把账号管理器透传挂到实例供登录用
        if self.ctx and self.ctx.account_manager:
            try:
                self.account_manager = self.ctx.account_manager
            except Exception:
                pass
        if self.config.need_sniff_network and not self._unbind_net_rules:
            self._net_note_event = asyncio.Event()
            self._unbind_net_rules = await bind_network_rules(self.page, self)

    async def _ensure_logged_in(self) -> bool:
        if not self.page:
            return False
        # 1) 优先尝试 Cookie 登录
        if await self._try_cookie_login():
            return True
        # 2) 回退手动登录
        logger.info("需要手动登录，正在打开登录页…")
        return await self._manual_login()

    async def _is_logged_in(self) -> bool:
        if not self.page:
            return False
        try:
            avatar = await wait_until_result(
                lambda: self.page.query_selector('.reds-img-box'),
                timeout=1000
            )
            return avatar is not None
        except asyncio.TimeoutError:
            return False

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

    async def _to_favorite_page(self) -> None:
        await self.page.click('.user, .side-bar-component')
        await asyncio.sleep(1)
        await self.page.click(".sub-tab-list:nth-child(2)")

    async def _scroll_page_once(self, *, pause_ms: int = 800) -> bool:
        """Scroll the page down once and return whether the scroll height increased.

        Args:
            pause_ms: pause after scroll to allow content/network to load.
        """
        try:
            last_height = await self.page.evaluate("document.documentElement.scrollHeight")
            await self.page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            await asyncio.sleep(max(0.05, float(pause_ms) / 1000.0))
            new_height = await self.page.evaluate("document.documentElement.scrollHeight")
            return bool(new_height and last_height and new_height > last_height)
        except Exception:
            return False

    def set_stop_decider(self, decider: Callable[[Any, List[Any], Optional[Any], List[FavoriteItem], List[FavoriteItem], float, Dict[str, Any], Optional[ResponseView]], Any]) -> None:
        """Set a custom stop-decider callback for network-driven collection.

        The callback signature:
            async def decider(
                page: Any,
                all_raw_responses: List[Any],
                last_raw_response: Optional[Any],
                all_parsed_items: List[FavoriteItem],
                last_batch_parsed_items: List[FavoriteItem],
                elapsed_seconds: float,
                extra_config: Dict[str, Any],
                last_response_view: Optional[ResponseView],
            ) -> bool

        Return True to stop collection; False to continue.
        """
        self._stop_decider = decider

    def _feed_state_like(self):
        class _State:
            def __init__(self, outer: "XiaohongshuPlugin") -> None:
                self.page = outer.page
                self.event = outer._net_note_event
                self.items = outer._net_note_items
                self.raw_responses = outer._net_responses
                self.last_raw_response = outer._net_last_response
                self.last_response_view = outer._net_last_response_view
        return _State(self)

    async def _collect_favorites_via_network(self) -> list[FavoriteItem]:
        # Build config/state and reuse shared collector
        extra = (self.config.extra if isinstance(self.config, TaskConfig) else {}) or {}
        cfg = FeedCollectionConfig(
            max_items=int(extra.get("max_items", 1000)),
            max_seconds=int(extra.get("max_seconds", 600)),
            max_idle_rounds=int(extra.get("max_idle_rounds", 2)),
            auto_scroll=bool(extra.get("auto_scroll", True)),
            scroll_pause_ms=int(extra.get("scroll_pause_ms", 800)),
        )
        state = FeedCollectionState[FavoriteItem](
            page=self.page,
            event=self._net_note_event or asyncio.Event(),
            items=self._net_note_items,
            raw_responses=self._net_responses,
            last_raw_response=self._net_last_response,
            last_response_view=self._net_last_response_view,
            stop_decider=self._stop_decider,
        )

        async def goto_first() -> None:
            await self._to_favorite_page()

        async def on_scroll() -> None:
            await self._scroll_page_once(pause_ms=cfg.scroll_pause_ms)

        results = await run_network_collection(
            state,
            cfg,
            extra_config=extra,
            goto_first=goto_first,
            on_scroll=on_scroll,
            key_fn=lambda it: getattr(it, "id", None),
        )
        # Keep the shared event linked back
        self._net_note_event = state.event
        return results

    async def _get_favorites(self) -> list[FavoriteItem]:
        if not self.page:
            logger.error("Page 未注入")
            return []
        try:
            notes: List[FavoriteItem] = []
            if getattr(self.config, "need_sniff_network", True):
                # Network-driven collection with stop conditions
                collected = await self._collect_favorites_via_network()
                notes = [asdict(n) if not isinstance(n, dict) else n for n in collected]
            else:
                # DOM scraping with a single pass fallback
                await self._to_favorite_page()
                await asyncio.sleep(1)
                items = await self.page.query_selector_all(".tab-content-item:nth-child(2) .note-item")
                if not items:
                    logger.warning("未找到收藏项，可能是DOM结构变化或未登录")
                    try:
                        await self.page.screenshot(path="debug_xiaohongshu_favorites.png")
                    except Exception:  # noqa: BLE001
                        pass
                    return []
                logger.info("开始获取收藏夹内容")
                for item in items:
                    await asyncio.sleep(1)
                    parsed = await self._parse_note_from_dom(item)
                    if parsed:
                        notes.append(asdict(parsed))

            logger.info(f"获取到 {len(notes)} 个收藏项")
            return notes
        except Exception as exc:  # noqa: BLE001
            logger.error(f"获取收藏夹失败: {exc}")
            try:
                await self.page.screenshot(path="error_xiaohongshu_favorites.png")
            except Exception:  # noqa: BLE001
                pass
            return []

    async def _parse_id(self, item: Any) -> Optional[str]:
        item_id = f"unknown_{datetime.now().timestamp()}"
        item_anchor = await item.query_selector("a")
        if item_anchor:
            item_link = await item_anchor.get_attribute("href")
            item_id = item_link.split("/")[-1]
        logger.info(f"读取笔记ID: {item_id}")
        return item_id

    async def _parse_title(self, note_container: Any) -> Optional[str]:
        title_val = "无标题"
        title_ele = await note_container.query_selector("#detail-title")
        if title_ele:
            title_val = await title_ele.text_content()
        logger.info(f"读取笔记标题: {title_val}")
        return title_val

    async def _parse_author(self, note_container: Any) -> tuple[str | Any, str | Any]:
        author_avatar_val = "空图片地址"
        author_avatar_ele = await note_container.query_selector(".avatar-item")
        if author_avatar_ele:
            author_avatar_val = await author_avatar_ele.get_attribute("src")
        logger.info(f"读取笔记作者头像: {author_avatar_val}")

        author_username_val = "空用户名"
        author_username_ele = await note_container.query_selector(".username")
        if author_username_ele:
            author_username_val = await author_username_ele.text_content()
        logger.info(f"读取笔记作者用户名: {author_username_val}")

        return author_avatar_val, author_username_val

    async def _parse_tag_list(self, note_container: Any) -> list[Any]:
        tag_ele_list = await note_container.query_selector_all(".note-text > .tag")
        tag_val_list = []
        if tag_ele_list:
            for tag_ele in tag_ele_list:
                tag_val = await tag_ele.text_content()
                tag_val_list.append(tag_val)
        logger.info(f"读取笔记标签: {tag_val_list}")
        return tag_val_list

    async def _parse_date_ip(self, note_container: Any) -> tuple[str | Any, str | Any]:
        date_ip_ele = await note_container.query_selector(".date")
        date_val = "空"
        ip_zh_val = "空"
        if date_ip_ele:
            date_ip_val = await date_ip_ele.text_content()
            datas = date_ip_val.split()
            if len(datas) == 1:
                date_val = datas[0]
            elif len(datas) == 2:
                if "创建" in datas[0] or "编辑" in datas[0]:
                    date_val = datas[1]
                else:
                    date_val = datas[0]
                    ip_zh_val = datas[1]

        logger.info(f"读取笔记创建时间: {date_val}")
        logger.info(f"读取笔记IP地址: {ip_zh_val}")
        return date_val, ip_zh_val

    async def _parse_comment_num(self, note_container: Any) -> int:
        comment_num_val = 0
        comment_num_ele = await note_container.query_selector(".total")
        if comment_num_ele:
            comment_num_val = await comment_num_ele.text_content()
        logger.info(f"读取笔记评论数量: {comment_num_val}")
        return comment_num_val

    async def _parse_statistic(self, note_container: Any) -> tuple[int | Any, int | Any, int | Any]:
        like_num_val = 0
        collect_num_val = 0
        chat_num_val = 0
        statistic_container = await wait_until_result(
            lambda: note_container.query_selector(".engage-bar-style"),
            timeout=1000
        )
        if statistic_container:
            like_num_ele = await statistic_container.query_selector(".like-wrapper > .count")
            if like_num_ele:
                like_num_val = await like_num_ele.text_content()
            collect_num_ele = await statistic_container.query_selector(".collect-wrapper > .count")
            if collect_num_ele:
                collect_num_val = await collect_num_ele.text_content()
            chat_num_ele = await statistic_container.query_selector(".chat-wrapper > .count")
            if chat_num_ele:
                chat_num_val = await chat_num_ele.text_content()
        logger.info(f"读取笔记数据：点赞数量={like_num_val} 收藏数量={collect_num_val} 评论数量={chat_num_val}")
        return like_num_val, collect_num_val, chat_num_val

    async def _parse_note_from_dom(self, item: ElementHandle) -> Optional[FavoriteItem]:
        # 点击笔记，查看笔记详情
        cover_ele = await item.query_selector(".title")
        await cover_ele.click()
        await asyncio.sleep(0.5)
        logger.info("点击笔记")

        # 1) id
        item_id: Optional[str] = await self._parse_id(item)

        note_container = await wait_until_result(
            lambda: item.query_selector(".note-detail-mask"),
            timeout=2000
        )

        # 2) title
        title_val = await self._parse_title(note_container)

        # 3) author
        author_avatar_val, author_username_val = await self._parse_author(note_container)

        # 4) tag
        tag_ele_list = await self._parse_tag_list(note_container)

        # 5) date & IP地址（中文）
        date_val, ip_zh_val = await self._parse_date_ip(note_container)

        # 6) comment_num
        comment_num_val = await self._parse_comment_num(note_container)

        # 7) statistic
        like_num_val, collect_num_val, chat_num_val = await self._parse_statistic(note_container)

        # 8) image


        # 9) video


        # 10) close note
        close_ele = await item.query_selector(".close-circle")
        await close_ele.click(timeout=2000)

        logger.info("\n\n")

        return FavoriteItem(
            id=item_id,
            title=title_val,
            author_info=AuthorInfo(username=author_username_val, avatar=author_avatar_val, user_id=None),
            tags=tag_ele_list,
            date=date_val,
            ip_zh=ip_zh_val,
            comment_num=comment_num_val,
            statistic=NoteStatistics(like_num=like_num_val, collect_num=collect_num_val, chat_num=chat_num_val),
            images=None,
            video=None,
            timestamp=datetime.now().isoformat(),
        )

    async def _parse_note_from_network(self, resp_data: Dict[str, Any]) -> Optional[FavoriteItem]:
        if not resp_data:
            return None
        items = resp_data if isinstance(resp_data, list) else [resp_data]
        for note_item in items:
            try:
                id = note_item["id"]
                note_card = note_item["note_card"]
                title = note_card.get("title")
                user = note_card.get("user", {})
                author_info = AuthorInfo(
                    username=user.get("nickname"),
                    avatar=user.get("avatar"),
                    user_id=user.get("user_id"),
                )
                tag_list = [tag.get("name") for tag in note_card.get("tag_list", [])]
                date = note_card.get("time")
                ip_zh = note_card.get("ip_location")
                interact = note_card.get("interact_info", {})
                comment_num = str(interact.get("comment_count", 0))
                statistic = NoteStatistics(
                    like_num=int(interact.get("liked_count", 0)),
                    collect_num=int(interact.get("collected_count", 0)),
                    chat_num=int(comment_num or 0),
                )
                images = [image.get("url_default") for image in note_card.get("image_list", [])]
                self._net_note_items.append(FavoriteItem(
                    id=id,
                    title=title,
                    author_info=author_info,
                    tags=tag_list,
                    date=date,
                    ip_zh=ip_zh,
                    comment_num=comment_num,
                    statistic=statistic,
                    images=images,
                    video=None,
                    timestamp=datetime.now().isoformat(),
                ))
            except Exception:
                continue
        if self._net_note_event:
            try:
                self._net_note_event.set()
            except Exception:
                pass

    # -----------------------------
    # 基于装饰器的网络规则示例（可按需新增多个，互相独立）
    # -----------------------------
    @net_rule_match(r".*/feed", kind="response")
    async def _get_note_details(self, rule: RuleContext, response: ResponseView):
        try:
            data = response.data()
            if data and data.get("code") == 0:
                # 记录原始响应并唤醒
                feed_record_response(self._feed_state_like(), data, response)
                asyncio.create_task(self._parse_note_from_network(data["data"]["items"]))
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"_get_note_details failed: {exc}")

    @net_rule_match(r".*\.mp4.*", kind="response")
    async def _capture_mp4_ranges(self, rule: RuleContext, response: ResponseView):
        try:
            if not self._video_session:
                return
            done_path = await self._video_session.on_response(rule, response)
            if done_path:
                logger.info(f"视频已下载完成: {done_path}")
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"_capture_mp4_ranges failed: {exc}")

    # @net_rule_match(r".*", kind="request")
    # async def _capture_requests(self, rule: RuleContext, request: RequestView):
    #     try:
    #         print(request.url)
    #     except Exception as exc:
    #         logger.debug(f"_capture_requests failed: {exc}")

    # -----------------------------
    # 辅助：从任意 dict/list 结构里提取第一个 mp4 链接
    # -----------------------------
    def _find_first_mp4_url(self, data: Any) -> Optional[str]:
        try:
            if isinstance(data, str):
                m = re.search(r"https?://[^\s'\"]+?\.mp4(?:\?[^'\"]*)?", data, re.IGNORECASE)
                return m.group(0) if m else None
            if isinstance(data, dict):
                for v in data.values():
                    url = self._find_first_mp4_url(v)
                    if url:
                        return url
            if isinstance(data, list):
                for v in data:
                    url = self._find_first_mp4_url(v)
                    if url:
                        return url
        except Exception:
            return None
        return None


@register_plugin("xiaohongshu")
def create_xhs(ctx: PluginContext, config: TaskConfig) -> XiaohongshuPlugin:
    p = XiaohongshuPlugin()
    p.configure(config)
    # 注入上下文（包含 page/account_manager）
    p.set_context(ctx)
    return p
