from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List


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