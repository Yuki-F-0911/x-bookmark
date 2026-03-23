"""
共通データクラス定義
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Bookmark:
    """X（旧Twitter）のブックマーク済みツイート"""
    id: str
    text: str
    author_name: str
    author_username: str
    url: str
    created_at: Optional[datetime] = None
    bookmarked_at: Optional[datetime] = None
    like_count: int = 0
    retweet_count: int = 0
    reply_count: int = 0
