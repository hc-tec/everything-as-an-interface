import asyncio
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..plugins.base import BasePlugin
from ..utils.browser import BrowserAutomation

logger = logging.getLogger("plugin.xiaohongshu")


# -----------------------------
# 常量与选择器
# -----------------------------
BASE_URL = "https://www.xiaohongshu.com"
LOGIN_URL = f"{BASE_URL}/login"

# 头像出现通常意味着已登录
AVATAR_SELECTORS: List[str] = [
    ".reds-avatar-border",
]

FAVORITE_ITEM_SELECTORS: List[str] = [
    ".note-item",
]

TITLE_SELECTORS: List[str] = [
    ".title",
    ".name",
    ".note-content",
    "h3",
    "h4",
]

AUTHOR_SELECTORS: List[str] = [
    ".author",
    ".nickname",
    ".user-name",
]

@dataclass
class AuthorInfo:
    username: str
    avatar: str

@dataclass
class NoteStatistics:
    like_num: int      # 点赞数量
    collect_num: int   # 收藏数量
    chat_num: int      # 评论数量

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
    comment_num: int
    statistic: NoteStatistics
    images: Optional[dict[str, str]]
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
        self.browser: Optional[BrowserAutomation] = None
        self.last_favorites: List[Dict[str, Any]] = []

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
        if self.browser:
            await self.browser.close()
            self.browser = None

    # -----------------------------
    # 公共流程入口
    # -----------------------------
    async def fetch(self) -> Dict[str, Any]:
        await self._ensure_browser_started()

        try:
            if not await self._ensure_logged_in():
                return {
                    "success": False,
                    "message": "登录失败，请检查网络连接或重试",
                    "need_relogin": True,
                }

            favorites = await self._get_favorites()
            if not favorites:
                return {
                    "success": False,
                    "message": "获取收藏夹内容失败，可能是DOM结构变化或登录状态失效",
                    "favorites": [],
                }

            new_items: List[Dict[str, Any]] = []
            previous_ids = {item["id"] for item in self.last_favorites}
            for item in favorites:
                if item["id"] not in previous_ids:
                    new_items.append(item)

            self.last_favorites = favorites

            # 将本次输入也回显在结果中，便于链路使用
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
        finally:
            if self.browser:
                await self.browser.close()
                self.browser = None

    # -----------------------------
    # 配置校验
    # -----------------------------
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
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
    # 内部工具方法
    # -----------------------------
    async def _ensure_browser_started(self) -> None:
        if self.browser is None:
            headless: bool = bool(self.config.get("headless", False))
            self.browser = BrowserAutomation(headless=headless)
            await self.browser.start()

    async def _ensure_logged_in(self) -> bool:
        if not self.browser:
            logger.error("浏览器未初始化")
            return False

        # 优先尝试 Cookie 登录
        if await self._try_cookie_login():
            return True

        # 回退为手动登录
        logger.info("需要手动登录，正在打开登录页…")
        return await self._manual_login()

    async def _try_cookie_login(self) -> bool:
        if not self.browser:
            return False

        cookie_ids: List[str] = list(self.config.get("cookie_ids", []))
        try_local: bool = not cookie_ids

        # 配置提供 cookie_ids
        if getattr(self, "account_manager", None) and cookie_ids:
            try:
                merged = self.account_manager.merge_cookies(cookie_ids)
                if merged:
                    await self.browser.set_cookies(merged)
                    await self.browser.navigate(BASE_URL)
                    await asyncio.sleep(2)
                    if await self._is_logged_in():
                        logger.info("使用配置的 Cookie 登录成功")
                        return True
                    logger.warning("提供的 Cookie 未生效")
            except Exception as exc:  # noqa: BLE001
                logger.error(f"注入 Cookie 失败: {exc}")

        # 未提供 cookie_ids，则尝试本地已保存的该平台 Cookie
        if getattr(self, "account_manager", None) and try_local:
            try:
                metas = self.account_manager.list_cookies("xiaohongshu")
                valid_ids = [m["id"] for m in metas if m.get("status", "valid") == "valid"]
                if valid_ids:
                    merged = self.account_manager.merge_cookies(valid_ids)
                    if merged:
                        await self.browser.set_cookies(merged)
                        await self.browser.navigate(BASE_URL)
                        await asyncio.sleep(2)
                        if await self._is_logged_in():
                            logger.info("使用本地已保存的 Cookie 登录成功")
                            return True
            except Exception as exc:  # noqa: BLE001
                logger.error(f"加载本地 Cookie 失败: {exc}")

        return False

    async def _is_logged_in(self) -> bool:
        if not self.browser:
            return False
        for selector in AVATAR_SELECTORS:
            avatar = await self.browser.wait_for_selector(selector, timeout=1000)
            if avatar:
                return True
        return False

    async def _manual_login(self) -> bool:
        if not self.browser:
            return False
        try:
            await self.browser.navigate(LOGIN_URL)
            await asyncio.sleep(1)
            logger.info("请在浏览器中手动登录小红书，系统会自动检测登录状态…")

            for i in range(300):  # 最多等待 5 分钟
                await asyncio.sleep(1)
                if await self._is_logged_in():
                    logger.info("检测到登录成功")
                    try:
                        cookies = await self.browser.get_cookies()
                        if cookies and hasattr(self, "account_manager"):
                            cookie_id = self.account_manager.add_cookies(
                                "xiaohongshu", cookies, name="登录获取"
                            )
                            if cookie_id:
                                logger.info(f"Cookie 已保存: {cookie_id}")
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(f"获取或保存 Cookie 失败: {exc}")
                    return True

                if i % 30 == 0 and i > 0:
                    logger.info(f"等待登录中… ({i // 60}分{i % 60}秒)")

            logger.error("登录超时，请重试")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error(f"手动登录过程异常: {exc}")
            return False

    async def _to_favorite_page(self) -> None:
        # 点击“我”进入主页
        ele_me = await self.browser.click('.user, .side-bar-component')
        # 点击“收藏”
        await self.browser.click("span:text('收藏')")

    async def _get_favorites(self) -> List[Dict[str, Any]]:
        if not self.browser or not self.browser.page:
            logger.error("浏览器未初始化")
            return []
        # 上次最新的收藏项
        last_newest_favorite_item = self.input_data.get("last_newest_favorite_item", None)
        try:
            await self._to_favorite_page()
            await asyncio.sleep(2)

            notes: List[FavoriteItem] = []
            while True:
                # 小红书一次性只能获取到有限数量的笔记，需要不断的滚动来获取更多收藏的笔记
                items = await self.browser.page.query_selector_all(FAVORITE_ITEM_SELECTORS[0])

                if not items:
                    logger.warning("未找到收藏项，可能是DOM结构变化或未登录")
                    try:
                        await self.browser.screenshot("debug_xiaohongshu_favorites.png")
                    except Exception:  # noqa: BLE001
                        pass
                    return []

                for item in items:
                    await asyncio.sleep(1)
                    parsed = await self._parse_favorite_item(item)
                    if parsed:
                        notes.append(parsed)

            logger.info(f"获取到 {len(notes)} 个收藏项")
            return notes
        except Exception as exc:  # noqa: BLE001
            logger.error(f"获取收藏夹失败: {exc}")
            try:
                await self.browser.screenshot("error_xiaohongshu_favorites.png")
            except Exception:  # noqa: BLE001
                pass
            return []

    async def _parse_id(self, item: Any) -> Optional[str]:
        item_id = f"unknown_{datetime.now().timestamp()}"
        item_anchor = await item.query_selector("a")
        if item_anchor:
            item_link = await item_anchor.get_attribute("href")
            item_id = item_link.split("/")[-1]
        return item_id

    async def _parse_title(self, note_container: Any) -> Optional[str]:
        title_val = "无标题"
        title_ele = await note_container.query_selector("#detail-title")
        if title_ele:
            title_val = await title_ele.text_content()
        return title_val

    async def _parse_author(self, note_container: Any) -> tuple[str | Any, str | Any]:
        author_avatar_val = "空图片地址"
        author_avatar_ele = await note_container.query_selector(".avatar-item")
        if author_avatar_ele:
            author_avatar_val = await author_avatar_ele.get_attribute("src")

        author_username_val = "空用户名"
        author_username_ele = await note_container.query_selector(".username")
        if author_username_ele:
            author_username_val = await author_username_ele.text_content()

        return author_avatar_val, author_username_val

    async def _parse_tag_list(self, note_container: Any) -> list[Any]:
        tag_ele_list = await note_container.query_selector_all(".tag")
        tag_val_list = []
        if tag_ele_list:
            for tag_ele in tag_ele_list:
                tag_val = await tag_ele.text_content()
                tag_val_list.append(tag_val)

        return tag_val_list

    async def _parse_date_ip(self, note_container: Any) -> tuple[str | Any, str | Any]:
        date_ip_ele = await note_container.query_selector(".date")
        date_val = "空"
        ip_zh_val = "空"
        if date_ip_ele:
            date_ip_val = await date_ip_ele.text_content()
            date_val, ip_zh_val = date_ip_val.split()

        return date_val, ip_zh_val

    async def _parse_comment_num(self, note_container: Any) -> int:
        comment_num_val = 0
        comment_num_ele = await note_container.query_selector(".total")
        if comment_num_ele:
            comment_num_val = await comment_num_ele.text_content()
        return comment_num_val

    async def _parse_statistic(self, note_container: Any) -> tuple[int | Any, int | Any, int | Any]:
        like_num_val = 0
        collect_num_val = 0
        chat_num_val = 0
        statistic_container = await note_container.wait_for_selector(".left", timeout=1000)
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
        return int(like_num_val), int(collect_num_val), int(chat_num_val)

    async def _parse_favorite_item(self, item: Any) -> Optional[FavoriteItem]:
        # 点击帖子，查看帖子详情
        await item.click()

        async def handle_response(response):
            url = response.url
            if "note_id" in url:
                note_data = await response.json()
                logger.info(f"[发现笔记api] node_data={note_data} url={url}")

        self.browser.page.on("response", handle_response)
        
        # 1) id
        item_id: Optional[str] = await self._parse_id(item)

        note_container = await self.browser.wait_for_selector(".note-detail-mask", timeout=5000)

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


        # 9) vedio


        return FavoriteItem(
            id=item_id,
            title=title_val,
            author_info=AuthorInfo(username=author_username_val, avatar=author_avatar_val),
            tags=tag_ele_list,
            date=date_val,
            ip_zh=ip_zh_val,
            comment_num=comment_num_val,
            statistic=NoteStatistics(like_num=like_num_val, collect_num=collect_num_val, chat_num=chat_num_val),
            images=None,
            video=None,
            timestamp=datetime.now().isoformat(),
        )