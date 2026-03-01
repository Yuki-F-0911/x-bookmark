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


def _extract_tweet_id_from_url(url: str) -> str:
    """URL からツイートIDを抽出する。例: https://x.com/user/status/12345 → '12345'"""
    import re
    match = re.search(r"/status/(\d+)", url)
    return match.group(1) if match else ""


def _fetch_tweet_via_syndication(tweet_id: str) -> dict:
    """
    Twitter Syndication APIからツイート詳細を取得する。
    Article（長文投稿）のタイトル・プレビュー、引用ツイート、いいね数も取得可能。

    Returns:
        {"text": str, "article_title": str, "article_preview": str,
         "like_count": int, "retweet_count": int} or 空dictで失敗
    """
    import urllib.request
    import urllib.error

    api_url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=0"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
        logger.warning(f"Syndication API失敗 (ID={tweet_id}): {e}")
        return {}

    result = {
        "text": "",
        "article_title": "",
        "article_preview": "",
        "like_count": data.get("favorite_count", 0),
        "retweet_count": data.get("retweet_count", 0),
        "reply_count": data.get("conversation_count", 0),
    }

    # ツイート本文（t.co短縮URLを展開）
    tweet_text = data.get("text", "")
    for url_entity in data.get("entities", {}).get("urls", []):
        short = url_entity.get("url", "")
        expanded = url_entity.get("expanded_url", "")
        if short and expanded:
            tweet_text = tweet_text.replace(short, expanded)
    result["text"] = tweet_text.strip()

    # Article情報（長文投稿）
    article = data.get("article")
    if article:
        result["article_title"] = article.get("title", "")
        result["article_preview"] = article.get("preview_text", "")

    # 引用ツイート
    quoted = data.get("quoted_tweet")
    if quoted:
        qt_user = quoted.get("user", {}).get("screen_name", "")
        qt_text = quoted.get("text", "")
        if qt_text:
            result["text"] += f"\n[引用: @{qt_user}] {qt_text}"

    return result


def _fetch_tweet_text_from_url(url: str) -> str:
    """
    ツイートURLから本文を取得する。
    Syndication API → oEmbed API の順でフォールバック。
    """
    import urllib.request
    import re as _re

    # 1. Syndication API（Article・引用ツイート対応）
    tweet_id = _extract_tweet_id_from_url(url)
    if tweet_id:
        syn = _fetch_tweet_via_syndication(tweet_id)
        if syn:
            # Articleの場合はタイトル+プレビューを結合
            if syn.get("article_title"):
                parts = [syn["article_title"]]
                if syn.get("article_preview"):
                    parts.append(syn["article_preview"])
                return " — ".join(parts)
            text = syn.get("text", "")
            if text and not text.startswith("https://t.co/"):
                return text

    # 2. oEmbed API（フォールバック）
    try:
        import html as _html
        oembed_url = f"https://publish.twitter.com/oembed?url={urllib.request.quote(url, safe=':/?=&')}&omit_script=true"
        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        raw_html = _html.unescape(data.get("html", ""))
        p_match = _re.search(r'<p[^>]*>(.*?)</p>', raw_html, _re.DOTALL)
        text = p_match.group(1) if p_match else raw_html
        text = _re.sub(r'<[^>]+>', '', text)
        text = _re.sub(r'pic\.twitter\.com/\S+', '', text)
        text = _re.split(r'—\s*', text)[0].strip()
        if text and not text.startswith("https://t.co/") and len(text) > 10:
            return text
    except Exception:
        pass

    return ""


def _load_from_csv(filepath: str) -> list[Bookmark]:
    """
    CSV形式のブックマークファイルを読み込む。

    X Bookmarks Exporter の CSV 形式:
      Text, DisplayName, Username, Timestamp, Link
    汎用形式:
      id/tweet_id, text/content, screen_name/username, created_at/timestamp, url/tweet_url
    """
    bookmarks: list[Bookmark] = []
    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # --- X Bookmarks Exporter 形式 (Text, DisplayName, Username, Timestamp, Link) ---
            link = (row.get("Link") or row.get("link") or "").strip()
            tweet_id = (
                row.get("id") or row.get("tweet_id") or row.get("ID") or
                _extract_tweet_id_from_url(link) or
                ""
            ).strip()
            if not tweet_id:
                continue

            text = (
                row.get("Text") or row.get("text") or
                row.get("content") or row.get("Content") or ""
            ).strip()

            # Username: "@handle" 形式の @ を除去
            raw_username = (
                row.get("Username") or row.get("username") or
                row.get("screen_name") or "unknown"
            ).strip()
            author_username = raw_username.lstrip("@")

            author_name = (
                row.get("DisplayName") or row.get("display_name") or
                row.get("name") or row.get("author_name") or author_username
            ).strip()

            url = link or f"https://x.com/{author_username}/status/{tweet_id}"

            created_at = _parse_datetime(
                row.get("Timestamp") or row.get("timestamp") or
                row.get("created_at") or row.get("CreatedAt")
            )

            bookmarks.append(Bookmark(
                id=tweet_id,
                text=text,
                author_name=author_name,
                author_username=author_username,
                url=url,
                created_at=created_at,
            ))

    # Text が空のものはSyndication API→oEmbed APIで本文を補完
    empty_count = sum(1 for bm in bookmarks if not bm.text)
    if empty_count > 0:
        logger.info(f"Text未取得 {empty_count} 件のツイート本文をAPIから補完します...")
        import time as _time
        for bm in bookmarks:
            if not bm.text and bm.url:
                tweet_id = _extract_tweet_id_from_url(bm.url)
                # Syndication APIから本文+メタデータを取得
                if tweet_id:
                    syn = _fetch_tweet_via_syndication(tweet_id)
                    if syn:
                        # エンゲージメント情報も補完
                        if syn.get("like_count") and not bm.like_count:
                            bm.like_count = syn["like_count"]
                        if syn.get("retweet_count") and not bm.retweet_count:
                            bm.retweet_count = syn["retweet_count"]
                        if syn.get("reply_count") and not bm.reply_count:
                            bm.reply_count = syn["reply_count"]
                        # Articleの場合
                        if syn.get("article_title"):
                            bm.text = f"{syn['article_title']} - {syn.get('article_preview', '')}"
                            t_title = syn['article_title'].encode('cp932', errors='replace').decode('cp932')
                            logger.info(f"  補完成功(Article): @{bm.author_username} ({t_title[:30]}...)")
                            _time.sleep(0.3)
                            continue
                        # 通常ツイート
                        text = syn.get("text", "")
                        if text and not text.startswith("https://t.co/"):
                            bm.text = text
                            logger.info(f"  補完成功(API): @{bm.author_username} ({bm.text[:50]}...)")
                            _time.sleep(0.3)
                            continue
                # フォールバック: _fetch_tweet_text_from_url
                fetched = _fetch_tweet_text_from_url(bm.url)
                if fetched:
                    bm.text = fetched
                    logger.info(f"  補完成功(oEmbed): @{bm.author_username} ({bm.text[:50]}...)")
                else:
                    logger.info(f"  補完失敗: @{bm.author_username} ({bm.url})")
                _time.sleep(0.3)

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

    # 拡張子だけでなく内容の先頭文字でも判別する
    # （.json でも CSV が入っている場合があるため）
    with open(filepath, "r", encoding="utf-8-sig") as f:
        first_char = f.read(1).strip()

    ext = os.path.splitext(filepath)[1].lower()
    is_csv = ext == ".csv" or (first_char not in ("[", "{") and first_char != "")

    if is_csv:
        logger.info("CSV形式として読み込みます")
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
    IDが増えすぎないよう最新100000件のみ保持する。
    """
    existing = load_processed_ids(filepath)
    all_ids = list(existing | ids)
    
    # IDを数値として評価し、降順でソート（文字列のままだと "9" > "10" になるバグを防止）
    # 万が一数値化できないIDがあってもエラーにならないようにフォールバック
    def _sort_key(x: str) -> int:
        try:
            return int(x)
        except ValueError:
            return 0
            
    # 最新100000件に制限
    all_ids_sorted = sorted(all_ids, key=_sort_key, reverse=True)[:100000]

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
