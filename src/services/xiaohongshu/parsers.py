from __future__ import annotations

import asyncio
import datetime
# 导入统一的日志配置
from src.config import get_logger
import re
from typing import Any, Dict, List, Optional

from glom import glom
from playwright.async_api import ElementHandle

from .models import AuthorInfo, NoteStatistics, NoteDetailsItem, NoteBriefItem, VideoInfo

logger = get_logger(__name__)


def quick_extract_initial_state(html_content: str) -> Optional[str]:
    """
    快速提取HTML文件中的window.__INITIAL_STATE__

    Args:
        html_content (str): HTML文档
    
    Returns:
        Optional[str]: 提取到的状态值，如果未找到则返回None
    """
    pattern = r'<script[^>]*>.*?window\.__INITIAL_STATE__\s*=\s*(.+?)(?=\s*;|\s*</script>|\s*$).*?</script>'
    
    match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
    
    if match:
        state_value = match.group(1).strip()
        logger.debug("找到 window.__INITIAL_STATE__:")
        return state_value
    return None


def parse_brief_from_network(resp_items: List[Dict[str, Any]]) -> List[NoteBriefItem]:
    """
    从网络响应中解析笔记简要信息

    Args:
        resp_items: 网络响应中的笔记列表

    Returns:
        List[NoteBriefItem]: 解析后的笔记简要信息列表
    """
    results: List[NoteBriefItem] = []
    for note_item in resp_items or []:
        try:
            id = note_item["note_id"]
            title = note_item.get("display_title")
            xsec_token = note_item.get("xsec_token")
            user = note_item.get("user", {})
            author_info = AuthorInfo(
                username=user.get("nickname"),
                avatar=user.get("avatar"),
                user_id=user.get("user_id"),
                xsec_token=user.get("xsec_token")
            )
            interact = note_item.get("interact_info", {})
            statistic = NoteStatistics(
                like_num=str(interact.get("liked_count", 0)),
                collect_num=None,
                chat_num=None
            )
            cover_image = note_item.get("cover", {}).get("url_default")
            results.append(
                NoteBriefItem(
                    id=id,
                    xsec_token=xsec_token,
                    title=title,
                    author_info=author_info,
                    statistic=statistic,
                    cover_image=cover_image,
                )
            )
        except Exception as e:
            logger.error(f"解析笔记信息出错：{str(e)}")
    return results


def parse_details_from_network(note_item: Dict[str, Any]) -> List[NoteDetailsItem]:
    """
    从网络响应中解析笔记详细信息

    Args:
        note_item: 笔记详细信息字典

    Returns:
        List[NoteDetailsItem]: 解析后的笔记详细信息列表
    """
    results: List[NoteDetailsItem] = []
    if not note_item:
        return results
        
    try:
        id = note_item["noteId"]
        title = note_item.get("title")
        desc = note_item.get("desc")
        user = note_item.get("user", {})
        author_info = AuthorInfo(
            username=user.get("nickname"),
            avatar=user.get("avatar"),
            user_id=user.get("userId"),
            xsec_token=user.get("xsecToken"),
        )
        tag_list = [tag.get("name") for tag in note_item.get("tagList", [])]
        date = note_item.get("time")
        ip_zh = note_item.get("ipLocation")
        interact = note_item.get("interactInfo", {})
        comment_num = str(interact.get("commentCount", 0))
        statistic = NoteStatistics(
            like_num=str(interact.get("likedCount", 0)),
            collect_num=str(interact.get("collectedCount", 0)),
            chat_num=str(interact.get("commentCount", 0)),
        )
        images = [
            image.get("urlDefault").replace("\\u002F", "/") 
            for image in note_item.get("imageList", [])
            if image.get("urlDefault")
        ]
        video = note_item.get("video", None)
        video_info = None
        if video:
            duration_sec = video.get("capa", {}).get("duration")
            src = glom(video, ("media.stream.h265.0.masterUrl"), default=None)
            if src:
                src = src.replace("\\u002F", "/")
            video_id = video.get("media", {}).get("videoId")
            video_info = VideoInfo(id=video_id, src=src, duration_sec=duration_sec)
        
        results.append(
            NoteDetailsItem(
                id=id,
                title=title,
                desc=desc,
                author_info=author_info,
                tags=tag_list,
                date=date,
                ip_zh=ip_zh,
                comment_num=comment_num,
                statistic=statistic,
                images=images,
                video=video_info,
                timestamp=datetime.datetime.now().isoformat(),
            )
        )
    except Exception as e:
        logger.error("note parse error", exc_info=e)
    return results


async def parse_details_from_dom(item: ElementHandle) -> Optional[NoteDetailsItem]:
    """
    从DOM元素中解析笔记详细信息

    Args:
        item: DOM元素句柄

    Returns:
        Optional[NoteDetailsItem]: 解析后的笔记详细信息，失败时返回None
    """
    try:
        # 点击笔记查看详情
        cover_ele = await item.query_selector(".title")
        if cover_ele:
            await cover_ele.click()
            await asyncio.sleep(0.4)

        # 辅助函数
        async def get_text(ele, default=""):
            return await ele.text_content() if ele else default

        async def get_attr(ele, name, default=""):
            return await ele.get_attribute(name) if ele else default

        # 解析笔记ID
        item_id = "unknown"
        item_anchor = await item.query_selector("a")
        if item_anchor:
            link = await item_anchor.get_attribute("href")
            if link:
                item_id = link.split("/")[-1]

        # 查找笔记详情容器
        note_container = await item.query_selector(".note-detail-mask")
        
        # 解析标题
        title_ele = await note_container.query_selector("#detail-title") if note_container else None
        title_val = await get_text(title_ele) if title_ele else ""

        # 解析作者信息
        avatar_ele = await note_container.query_selector(".avatar-item") if note_container else None
        avatar_val = await get_attr(avatar_ele, "src") if avatar_ele else ""
        
        username_ele = await note_container.query_selector(".username") if note_container else None
        username_val = await get_text(username_ele) if username_ele else ""

        # 解析标签
        tag_ele_list = await note_container.query_selector_all(".note-text > .tag") if note_container else []
        tags: List[str] = []
        for tag_ele in tag_ele_list or []:
            txt = await tag_ele.text_content()
            if txt:
                tags.append(txt)

        # 解析日期和IP
        date_ele = await note_container.query_selector(".date") if note_container else None
        date_val = ""
        ip_zh_val = ""
        if date_ele:
            date_ip_val = await date_ele.text_content()
            if date_ip_val:
                parts = date_ip_val.split()
                if len(parts) == 1:
                    date_val = parts[0]
                elif len(parts) >= 2:
                    if "创建" in parts[0] or "编辑" in parts[0]:
                        date_val = parts[1]
                    else:
                        date_val = parts[0]
                        ip_zh_val = parts[1]

        # 解析评论数
        comment_ele = await note_container.query_selector(".total") if note_container else None
        comment_val = await get_text(comment_ele) if comment_ele else "0"

        # 解析统计信息
        engage = await note_container.query_selector(".engage-bar-style") if note_container else None
        like_val = collect_val = chat_val = "0"
        if engage:
            like_ele = await engage.query_selector(".like-wrapper > .count")
            collect_ele = await engage.query_selector(".collect-wrapper > .count")
            chat_ele = await engage.query_selector(".chat-wrapper > .count")
            like_val = await get_text(like_ele) if like_ele else "0"
            collect_val = await get_text(collect_ele) if collect_ele else "0"
            chat_val = await get_text(chat_ele) if chat_ele else "0"

        # 关闭详情弹框
        close_ele = await item.query_selector(".close-circle")
        if close_ele:
            try:
                await close_ele.click(timeout=2000)
            except Exception:
                pass

        return NoteDetailsItem(
            id=item_id,
            title=title_val,
            desc="",  # DOM解析暂不支持描述内容
            author_info=AuthorInfo(
                username=username_val, 
                avatar=avatar_val, 
                user_id=None,
                xsec_token=""
            ),
            tags=tags,
            date=date_val,
            ip_zh=ip_zh_val,
            comment_num=comment_val,
            statistic=NoteStatistics(
                like_num=like_val, 
                collect_num=collect_val, 
                chat_num=chat_val
            ),
            images=None,
            video=None,
            timestamp=datetime.datetime.now().isoformat(),
        )
    except Exception:
        return None