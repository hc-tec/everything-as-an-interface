from dataclasses import dataclass
from typing import Optional, Any, List

from src.services.models import WithRaw, AuthorInfo


@dataclass
class FavoriteVideoItem(WithRaw):
    id: str
    bvid: str
    collection_id: str # 所属的收藏夹ID
    cover: str
    ctime: str
    pubtime: str
    fav_time: str
    duration_sec: int
    intro: str
    title: str
    creator: AuthorInfo
