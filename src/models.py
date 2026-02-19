"""
共通データクラス定義
"""

from dataclasses import dataclass, field
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


@dataclass
class WebResult:
    """Web検索（DuckDuckGo等）の結果1件"""
    title: str
    url: str
    snippet: str


@dataclass
class EnrichedBookmark:
    """要約・カテゴリ・Web補足情報が付与されたブックマーク"""
    bookmark: Bookmark
    category: str = "その他"
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    web_results: list[WebResult] = field(default_factory=list)
    enrichment_summary: str = ""


@dataclass
class DigestResult:
    """1日分のダイジェスト全体"""
    date: datetime
    bookmarks: list[EnrichedBookmark]
    total_count: int
    model_used: str
    token_usage: dict = field(default_factory=dict)
