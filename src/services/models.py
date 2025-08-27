'''
存放通用的 model
'''
from dataclasses import dataclass
from typing import Optional, Any, List


@dataclass
class WithRaw:
    raw_data: Optional[Any] # 保留原始数据（JSON、dict、甚至是未加工字符串）


@dataclass
class UserInfo:
    user_id: str
    username: str
    avatar: str
    xsec_token: Optional[str] = None
    gender: Optional[str] = None
    is_following: Optional[bool] = None
    is_followed: Optional[bool] = None
    user_type: Optional[str] = None


@dataclass
class AuthorInfo(UserInfo):
    pass


@dataclass
class NoteStatistics:
    like_num: str      # 点赞数量
    collect_num: str   # 收藏数量
    chat_num: str      # 评论数量

@dataclass
class VideoInfo:
    duration_sec: int
    src: str
    id: str

@dataclass
class NoteDetailsItem(WithRaw):
    id: str
    xsec_token: str
    title: str
    desc: str
    author_info: AuthorInfo
    tags: List[str]
    date: str
    ip_zh: str
    comment_num: str
    statistic: NoteStatistics
    images: Optional[list[str]]
    video: Optional[VideoInfo]
    timestamp: str

@dataclass
class NoteAccessInfo:
    id: str
    xsec_token: str


@dataclass
class NoteBriefItem(WithRaw):
    id: str
    xsec_token: str
    title: str
    author_info: AuthorInfo
    statistic: NoteStatistics
    cover_image: str


# 收藏夹
@dataclass
class CollectionItem(WithRaw):
    id: str
    title: str
    description: Optional[str]
    link: str  # 收藏夹链接
    item_count: int # 收藏夹中的项数量
    is_default: bool  # 是否为默认收藏夹
    creator: AuthorInfo
    created_time: int
    updated_time: int


