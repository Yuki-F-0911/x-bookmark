"""
ブックマークJSONファイルの読み込みモジュール。

対応フォーマット:
  - X Bookmarks Exporter (Chrome拡張) の出力JSON
  - twitter-web-exporter の出力JSON
  - CSV形式（汎用）

処理済みIDのキャッシュ管理（差分処理）も行う。
"""

import json
import csv
import os
from datetime import datetime, timezone
from typing import Optional
from .models import Bookmark
from .utils import get_logger

logger = get_logger(__name__)

PROCESSED_IDS_FILE = "processed_ids.json"


def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """ISO 8601 / Twitter日付文字列を datetime に変換"""
    if not dt_str:
        return None
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%a %b %d %H:%M:%S %z %Y",  # Twitter API 旧形式
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    logger.warning(f"日付のパースに失敗しました: {dt_str}")
    return None


def _load_from_json(filepath: str) -> list[Bookmark]:
    """
    JSON形式のブックマークファイルを読み込む。

    対応形式:
      1. X Bookmarks Exporter: [{id, text, user: {name, screen_name}, created_at, url, ...}]
      2. twitter-web-exporter: [{id_str, full_text, user: {...}, ...}]
      3. シンプル形式: [{id, text, author_name, author_username, url}]
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().strip()

    # ファイルが空の場合は空リストとして扱う
    if not content:
        logger.info(f"ブックマークファイルが空です: {filepath}")
        return []

    data = json.loads(content)

    if not isinstance(data, list):
        raise ValueError(f"JSONはリスト形式である必要があります。ファイル: {filepath}")

    bookmarks: list[Bookmark] = []
    for item in data:
        try:
            bookmark = _parse_json_item(item)
            if bookmark:
                bookmarks.append(bookmark)
        except Exception as e:
            logger.warning(f"アイテムのパースをスキップ: {e} | item={str(item)[:100]}")

    return bookmarks


def _parse_json_item(item: dict) -> Optional[Bookmark]:
    """JSON の1アイテムを Bookmark に変換"""
    # ID取得（複数の形式に対応）
    tweet_id = str(
        item.get("id")
        or item.get("id_str")
        or item.get("tweet_id")
        or ""
    )
    if not tweet_id:
        return None

    # テキスト取得
    text = (
        item.get("text")
        or item.get("full_text")
        or item.get("content")
        or ""
    )

    # ユーザー情報取得
    user = item.get("user") or {}
    author_name = (
        item.get("author_name")
        or user.get("name")
        or user.get("display_name")
        or "Unknown"
    )
    author_username = (
        item.get("author_username")
        or item.get("screen_name")
        or user.get("screen_name")
        or user.get("username")
        or "unknown"
    )

    # URL構築
    url = (
        item.get("url")
        or item.get("tweet_url")
        or f"https://x.com/{author_username}/status/{tweet_id}"
    )

    # 日付
    created_at = _parse_datetime(
        item.get("created_at") or item.get("timestamp")
    )

    # エンゲージメント指標
    metrics = item.get("public_metrics") or {}
    like_count = (
        int(item.get("like_count", 0))
        or int(item.get("favorite_count", 0))
        or int(metrics.get("like_count", 0))
    )
    retweet_count = (
        int(item.get("retweet_count", 0))
        or int(metrics.get("retweet_count", 0))
    )
    reply_count = (
        int(item.get("reply_count", 0))
        or int(metrics.get("reply_count", 0))
    )

    return Bookmark(
        id=tweet_id,
        text=text.strip(),
        author_name=author_name,
        author_username=author_username,
        url=url,
        created_at=created_at,
        like_count=like_count,
        retweet_count=retweet_count,
        reply_count=reply_count,
    )


def _load_from_csv(filepath: str) -> list[Bookmark]:
    """CSV形式のブックマークファイルを読み込む（汎用対応）"""
    bookmarks: list[Bookmark] = []
    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tweet_id = (
                row.get("id") or row.get("tweet_id") or row.get("ID") or ""
            ).strip()
            if not tweet_id:
                continue

            text = (row.get("text") or row.get("content") or row.get("Text") or "").strip()
            author_username = (
                row.get("screen_name") or row.get("username") or row.get("author_username") or "unknown"
            ).strip()
            author_name = (
                row.get("name") or row.get("author_name") or author_username
            ).strip()
            url = (
                row.get("url") or row.get("tweet_url") or
                f"https://x.com/{author_username}/status/{tweet_id}"
            ).strip()
            created_at = _parse_datetime(row.get("created_at") or row.get("timestamp"))

            bookmarks.append(Bookmark(
                id=tweet_id,
                text=text,
                author_name=author_name,
                author_username=author_username,
                url=url,
                created_at=created_at,
            ))
    return bookmarks


def load_bookmarks(filepath: str) -> list[Bookmark]:
    """
    JSON または CSV ファイルからブックマークを読み込む。
    重複（同一ID）は自動的に除去される。

    Args:
        filepath: ブックマークファイルのパス

    Returns:
        Bookmark のリスト（重複除去済み）

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: ファイル形式が不正な場合
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"ブックマークファイルが見つかりません: {filepath}\n"
            f"X Bookmarks Exporter でエクスポートした JSON を {filepath} に配置してください。"
        )

    # ファイルサイズが0の場合は空リストを返す
    if os.path.getsize(filepath) == 0:
        logger.info(f"ブックマークファイルが空です（0バイト）: {filepath}")
        return []

    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        bookmarks = _load_from_csv(filepath)
    else:
        bookmarks = _load_from_json(filepath)

    # 重複除去（ID基準、最初のものを残す）
    seen_ids: set[str] = set()
    unique_bookmarks: list[Bookmark] = []
    for bm in bookmarks:
        if bm.id not in seen_ids:
            seen_ids.add(bm.id)
            unique_bookmarks.append(bm)

    logger.info(f"{len(unique_bookmarks)} 件のブックマークを読み込みました（重複除去後）")
    return unique_bookmarks


def load_processed_ids(filepath: str = PROCESSED_IDS_FILE) -> set[str]:
    """
    処理済みツイートIDのセットをファイルから読み込む。
    ファイルが存在しない場合は空セットを返す。
    """
    if not os.path.exists(filepath):
        return set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("ids", []))
    except Exception as e:
        logger.warning(f"処理済みIDファイルの読み込みに失敗: {e}")
        return set()


def save_processed_ids(ids: set[str], filepath: str = PROCESSED_IDS_FILE) -> None:
    """
    処理済みツイートIDをファイルに保存する。
    IDが増えすぎないよう最新1000件のみ保持する。
    """
    existing = load_processed_ids(filepath)
    all_ids = list(existing | ids)
    # 最新1000件に制限（IDは数値が大きいほど新しい）
    all_ids_sorted = sorted(all_ids, reverse=True)[:1000]

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"ids": all_ids_sorted}, f, ensure_ascii=False, indent=2)
    logger.info(f"処理済みID を保存しました: {len(all_ids_sorted)} 件")


def filter_new_bookmarks(
    bookmarks: list[Bookmark],
    processed_ids: set[str],
) -> list[Bookmark]:
    """
    処理済みIDを除外した新規ブックマークのみを返す。
    """
    new_bookmarks = [bm for bm in bookmarks if bm.id not in processed_ids]
    skipped = len(bookmarks) - len(new_bookmarks)
    if skipped > 0:
        logger.info(f"{skipped} 件は処理済みのためスキップ")
    return new_bookmarks
