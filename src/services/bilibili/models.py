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

@dataclass
class VideoStatistic:
    view: int
    danmaku: int
    reply: int
    favorite: int
    coin: int
    share: int
    like: int

@dataclass
class VideoDimension:
    width: int
    height: int
    rotate: int

@dataclass
class VideoUrl(WithRaw):
    id: str
    base_url: str
    backup_url: str
    bandwidth: int
    mime_type: str
    codecs: str
    width: int
    height: int
    frame_rate: str

@dataclass
class AudioUrl(WithRaw):
    id: str
    base_url: str
    backup_url: str
    bandwidth: int
    mime_type: str
    codecs: str

@dataclass
class BiliVideoDetails(WithRaw):
    id: str
    bvid: str
    cover: str
    ctime: str
    pubdate: str
    duration_sec: int
    intro: str
    title: str
    creator: AuthorInfo
    tname: str
    tname_v2: str
    stat: VideoStatistic
    tags: List[str]
    video_url: VideoUrl
    audio_url: AudioUrl
    dimension: VideoDimension

@dataclass
class VideoSubtitleItem:
    content: str
    from_: float
    to: float
    location: float
    sid: int

@dataclass
class VideoSubtitleList(WithRaw):
    subtitles: List[VideoSubtitleItem]
    lang: str
    type: str
