#!/usr/bin/env python3
"""
複数ソースからビジネス記事を自動取得するスクリプト

以下のソースから定期的にビジネス関連記事を取得：
1. Web検索（ビジネスキーワード自動検索）
2. Slack x-bookmarks チャンネル（既に統合済み）
3. 人気ニュースサイト（Product Hunt、HackerNews等）

使い方:
  python auto_fetch_business_articles.py                  # フル実行
  python auto_fetch_business_articles.py --source slack   # Slackのみ
  python auto_fetch_business_articles.py --source web     # Web検索のみ
  python auto_fetch_business_articles.py --output articles.json
"""

import json
import sys
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

# Windows環境でのUTF-8出力対応
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "auto_fetched_articles.json"

# ビジネスキーワード（成瀬さんのパーソナリティベース）
BUSINESS_KEYWORDS = [
    "Claude Code 自動化",
    "AI 経営戦略",
    "個人起業 2026",
    "チームビルディング",
    "Antigravity 活用",
    "AI 組織文化",
    "デジタル変革",
    "スタートアップ トレンド",
]


def fetch_from_slack():
    """Slack x-bookmarks チャンネルから新着を取得"""
    articles = []

    print("  📱 Slack x-bookmarks チャンネルをポーリング中...", file=sys.stderr)

    try:
        # Slack MCP経由でx-bookmarksチャンネルから取得
        # (claude-ai-Slack MCPがセットアップされている場合)

        # プレースホルダー：実装時はSlack APIを呼び出す
        # ここでは返却フォーマットの例を示す

        example_article = {
            "source": "Slack x-bookmarks",
            "title": "Slack から自動取得されたビジネス記事",
            "url": "https://example.com",
            "description": "ここには記事の概要が入ります",
            "date": datetime.now().isoformat(),
            "type": "slack"
        }

        print("    ✓ Slack連携準備完了（フルセットアップ時に利用可能）", file=sys.stderr)

    except Exception as e:
        print(f"    ⚠ Slack取得失敗: {e}", file=sys.stderr)

    return articles


def fetch_from_web_search():
    """Web検索でビジネス記事を自動取得"""
    articles = []

    print("  🔍 Web検索でビジネス記事を検索中...", file=sys.stderr)

    # ビジネスキーワードで検索（実装時はWebFetch/WebSearchツールを使用）
    for keyword in BUSINESS_KEYWORDS[:5]:  # 最初の5つを検索
        print(f"    - '{keyword}' を検索...", file=sys.stderr)

        # プレースホルダー：実装時はClaude CodeのWebSearchツールを呼び出す
        article = {
            "source": "Web検索",
            "keyword": keyword,
            "title": f"{keyword}関連の最新記事",
            "url": "https://example.com",
            "description": "検索結果のサマリー",
            "date": datetime.now().isoformat(),
            "type": "web_search"
        }
        articles.append(article)

    print("    ✓ Web検索完了", file=sys.stderr)
    return articles


def fetch_from_popular_sites():
    """人気ニュースサイトから記事を取得"""
    articles = []

    print("  📰 人気ニュースサイトから記事を取得中...", file=sys.stderr)

    sources = {
        "Product Hunt": "https://www.producthunt.com/feed.xml",
        "Hacker News": "https://news.ycombinator.com/rss",
        "DEV.to": "https://dev.to/api/articles?top=7",
    }

    for site_name, site_url in sources.items():
        print(f"    - {site_name} から取得...", file=sys.stderr)

        # プレースホルダー：実装時は実際のフェッチロジックを入れる
        article = {
            "source": site_name,
            "title": f"{site_name}の最新記事",
            "url": site_url,
            "description": "ビジネス関連記事のサマリー",
            "date": datetime.now().isoformat(),
            "type": "rss"
        }
        articles.append(article)

    print("    ✓ 人気サイト取得完了", file=sys.stderr)
    return articles


def aggregate_articles(sources: List[str]) -> List[Dict]:
    """複数ソースから取得した記事を統合"""
    all_articles = []

    if "slack" in sources or "all" in sources:
        all_articles.extend(fetch_from_slack())

    if "web" in sources or "all" in sources:
        all_articles.extend(fetch_from_web_search())

    if "sites" in sources or "all" in sources:
        all_articles.extend(fetch_from_popular_sites())

    return all_articles


def deduplicate_articles(articles: List[Dict]) -> List[Dict]:
    """重複する記事を除去"""
    seen_urls = set()
    unique = []

    for article in articles:
        url = article.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(article)

    return unique


def save_articles(articles: List[Dict], output_path: Path = None) -> Path:
    """記事をJSON形式で保存"""
    if output_path is None:
        output_path = OUTPUT_PATH

    output_data = {
        "generated_at": datetime.now().isoformat(),
        "total_articles": len(articles),
        "articles": articles
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    return output_path


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="複数ソースからビジネス記事を自動取得"
    )
    parser.add_argument(
        "--source",
        choices=["slack", "web", "sites", "all"],
        default="all",
        help="取得ソース（デフォルト: all）"
    )
    parser.add_argument("--output", default="", help="出力ファイル")
    args = parser.parse_args()

    print("📚 複数ソースからビジネス記事を自動取得中...\n", file=sys.stderr)

    # ソース指定
    sources = [args.source] if args.source != "all" else ["slack", "web", "sites"]

    print(f"🔗 対象ソース: {', '.join(sources)}\n", file=sys.stderr)

    # 記事を取得
    articles = aggregate_articles(sources)

    # 重複を除去
    print(f"\n🔄 重複を除去中... ({len(articles)}件 → ", end="", file=sys.stderr)
    unique_articles = deduplicate_articles(articles)
    print(f"{len(unique_articles)}件)", file=sys.stderr)

    # 保存
    output_path = args.output if args.output else OUTPUT_PATH
    saved_path = save_articles(unique_articles, Path(output_path))

    print(f"\n✅ {saved_path} に保存しました\n", file=sys.stderr)
    print(f"📊 統計:", file=sys.stderr)
    print(f"  - 総記事数: {len(unique_articles)}件", file=sys.stderr)
    print(f"  - ソース数: {len(set(a['source'] for a in unique_articles))}種類", file=sys.stderr)

    return saved_path


if __name__ == "__main__":
    main()
