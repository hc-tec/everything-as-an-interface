from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class CommentAuthor:
    user_id: Optional[str]
    username: Optional[str]
    avatar: Optional[str]


@dataclass
class CommentItem:
    id: str
    note_id: str
    author: CommentAuthor
    content: str
    like_num: int
    created_at: str


@dataclass
class SearchAuthor:
    user_id: Optional[str]
    username: Optional[str]
    avatar: Optional[str]


@dataclass
class SearchResultItem:
    id: str
    title: str
    author: SearchAuthor
    tags: List[str]
    url: str
    snippet: Optional[str]
    timestamp: str


@dataclass
class NoteDetail:
    """Complete detailed information about a note."""
    
    id: str
    title: str
    content: str
    author: SearchAuthor
    tags: List[str]
    images: List[str]
    video: Optional[str]
    like_count: int
    collect_count: int
    comment_count: int
    share_count: int
    view_count: Optional[int]
    created_at: str
    updated_at: Optional[str]
    ip_location: Optional[str]
    note_type: str  # "normal", "video", "live" etc.
    visibility: str  # "public", "private" etc.
    topic: Optional[str]
    location: Optional[str]
    music: Optional[str]
    extra_data: Optional[Dict[str, Any]] = None


@dataclass
class MediaInfo:
    """Information about media files for publishing."""
    
    file_path: str
    media_type: str  # "image", "video"
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None  # For videos
    size: Optional[int] = None  # File size in bytes
    

@dataclass
class PublishConfig:
    """Configuration for publishing content."""
    
    auto_tag: bool = True
    location_enabled: bool = False
    comment_enabled: bool = True
    allow_save: bool = True
    original_declaration: bool = False
    schedule_time: Optional[str] = None  # ISO format
    topic_id: Optional[str] = None


@dataclass
class AuthorInfo:
    user_id: str
    username: str
    avatar: str
    xsec_token: str

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
class NoteDetailsItem:
    id: str
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
class NoteBriefItem:
    id: str
    xsec_token: str
    title: str
    author_info: AuthorInfo
    statistic: NoteStatistics
    cover_image: str
