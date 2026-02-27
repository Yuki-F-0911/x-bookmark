"""
X(Twitter)投稿の本文を取得するスクリプト
Syndication API（メイン）+ oEmbed API（フォールバック）

使い方:
  python fetch_tweets.py                          # bookmarks.json の新しい順20件
  python fetch_tweets.py --limit 10               # 新しい順10件
  python fetch_tweets.py --url https://x.com/...  # 単一URL指定
  python fetch_tweets.py --output results.json    # JSON出力
"""

import argparse
import csv
import json
import html
import io
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Windows環境でのUTF-8出力対応
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

SYNDICATION_URL = "https://cdn.syndication.twimg.com/tweet-result?id={}&token=0"
OEMBED_URL = "https://publish.twitter.com/oembed?url={}&omit_script=true"
BOOKMARKS_PATH = Path(__file__).parent / "bookmarks.json"


def extract_tweet_id(url: str) -> str | None:
    """ツイートURLからIDを抽出"""
    m = re.search(r'/status/(\d+)', url)
    return m.group(1) if m else None


def fetch_syndication(tweet_id: str) -> dict | None:
    """Syndication APIからツイート詳細を取得（Article対応）"""
    api_url = SYNDICATION_URL.format(tweet_id)
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"  [Syndication失敗] ID={tweet_id}: {e}", file=sys.stderr)
        return None


def extract_from_syndication(data: dict) -> dict:
    """Syndication APIレスポンスからテキスト情報を抽出"""
    result = {
        "text": "",
        "article_title": "",
        "article_preview": "",
        "quote_text": "",
        "media_urls": [],
    }

    # ツイート本文
    tweet_text = data.get("text", "")
    # t.co短縮URLを展開
    for url_entity in data.get("entities", {}).get("urls", []):
        short = url_entity.get("url", "")
        expanded = url_entity.get("expanded_url", "")
        display = url_entity.get("display_url", "")
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
        qt_text = quoted.get("text", "")
        qt_user = quoted.get("user", {}).get("name", "")
        qt_screen = quoted.get("user", {}).get("screen_name", "")
        result["quote_text"] = f"[引用: @{qt_screen}({qt_user})] {qt_text}"

    # メディア
    for media in data.get("mediaDetails", []):
        if media.get("type") == "photo":
            result["media_urls"].append(media.get("media_url_https", ""))

    return result


def fetch_oembed(tweet_url: str) -> dict | None:
    """oEmbed APIからツイート情報を取得（フォールバック）"""
    api_url = OEMBED_URL.format(urllib.request.quote(tweet_url, safe=":/?=&"))
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None


def extract_text_from_oembed(data: dict) -> str:
    """oEmbedレスポンスのHTMLからテキストを抽出"""
    raw_html = html.unescape(data.get("html", ""))
    p_match = re.search(r'<p[^>]*>(.*?)</p>', raw_html, re.DOTALL)
    text = p_match.group(1) if p_match else raw_html
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'pic\.twitter\.com/\S+', '', text)
    text = re.split(r'—\s*', text)[0].strip()
    return text


def load_bookmarks(path: Path, limit: int = 20) -> list[dict]:
    """bookmarks.json(CSV形式)を読み込み、新しい順にソートして返す"""
    if not path.exists():
        print(f"エラー: {path} が見つかりません", file=sys.stderr)
        sys.exit(1)

    bookmarks = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bookmarks.append({
                "text": row.get("Text", ""),
                "display_name": row.get("DisplayName", ""),
                "username": row.get("Username", ""),
                "timestamp": row.get("Timestamp", ""),
                "link": row.get("Link", ""),
            })

    bookmarks.sort(key=lambda x: x["timestamp"], reverse=True)
    return bookmarks[:limit]


def fetch_tweet_content(bookmark: dict) -> dict:
    """1件のブックマークについてツイート本文を取得"""
    result = {
        "url": bookmark["link"],
        "username": bookmark["username"],
        "display_name": bookmark["display_name"],
        "timestamp": bookmark["timestamp"],
        "source": "",
        "text": "",
        "article_title": "",
        "article_preview": "",
        "quote_text": "",
    }

    tweet_id = extract_tweet_id(bookmark["link"])
    if not tweet_id:
        result["text"] = "[URL解析失敗]"
        result["source"] = "failed"
        return result

    # 1. Syndication API（メイン: Article・引用ツイート対応）
    syn_data = fetch_syndication(tweet_id)
    if syn_data:
        extracted = extract_from_syndication(syn_data)
        result["article_title"] = extracted["article_title"]
        result["article_preview"] = extracted["article_preview"]
        result["quote_text"] = extracted["quote_text"]

        # Articleの場合はタイトル+プレビューを主テキストに
        if extracted["article_title"]:
            result["text"] = extracted["text"]  # 元ツイート本文（URLだけの場合も）
            result["source"] = "syndication_article"
            return result

        # 通常ツイート
        if extracted["text"] and not extracted["text"].startswith("https://t.co/"):
            result["text"] = extracted["text"]
            result["source"] = "syndication"
            return result

    # 2. CSVテキスト（フォールバック）
    if bookmark["text"].strip():
        result["text"] = bookmark["text"].strip()
        result["source"] = "csv"
        return result

    # 3. oEmbed API（最終フォールバック）
    oembed_data = fetch_oembed(bookmark["link"])
    if oembed_data:
        text = extract_text_from_oembed(oembed_data)
        if text:
            result["text"] = text
            result["source"] = "oembed"
            return result

    result["text"] = "[取得失敗]"
    result["source"] = "failed"
    return result


def format_timestamp(ts: str) -> str:
    """ISO形式のタイムスタンプを読みやすい形式に変換"""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%m/%d %H:%M")
    except (ValueError, AttributeError):
        return ts


def main():
    parser = argparse.ArgumentParser(description="X投稿の本文を取得")
    parser.add_argument("--limit", type=int, default=20, help="取得件数（デフォルト: 20）")
    parser.add_argument("--url", type=str, help="単一のツイートURLを指定")
    parser.add_argument("--output", type=str, help="結果をJSONファイルに保存")
    parser.add_argument("--bookmarks", type=str, help="bookmarks.jsonのパス")
    args = parser.parse_args()

    results = []

    if args.url:
        bookmark = {
            "text": "",
            "display_name": "",
            "username": "",
            "timestamp": "",
            "link": args.url,
        }
        result = fetch_tweet_content(bookmark)
        results.append(result)
    else:
        bk_path = Path(args.bookmarks) if args.bookmarks else BOOKMARKS_PATH
        bookmarks = load_bookmarks(bk_path, args.limit)
        print(f"ブックマーク {len(bookmarks)} 件を処理中...\n", file=sys.stderr)

        for i, bk in enumerate(bookmarks, 1):
            result = fetch_tweet_content(bk)
            results.append(result)
            if i < len(bookmarks):
                time.sleep(0.3)

    # JSON出力
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"結果を {args.output} に保存しました", file=sys.stderr)

    # コンソール出力
    for i, r in enumerate(results, 1):
        ts = format_timestamp(r["timestamp"]) if r["timestamp"] else "N/A"
        src_map = {
            "syndication": "API",
            "syndication_article": "API(Article)",
            "csv": "CSV",
            "oembed": "oEmbed",
            "failed": "失敗",
        }
        src_label = src_map.get(r["source"], r["source"])
        print(f"--- {i}. {r['display_name']} ({r['username']}) [{ts}] [{src_label}] ---")
        print(f"URL: {r['url']}")

        # Article表示
        if r.get("article_title"):
            print(f"[Article] {r['article_title']}")
            if r.get("article_preview"):
                print(f"  {r['article_preview']}")

        # 本文
        text = r["text"]
        if len(text) > 500:
            text = text[:500] + "..."
        if text and not (r.get("article_title") and text.startswith("http")):
            print(f"{text}")

        # 引用ツイート
        if r.get("quote_text"):
            qt = r["quote_text"]
            if len(qt) > 300:
                qt = qt[:300] + "..."
            print(f"  {qt}")

        print()


if __name__ == "__main__":
    main()
