"""
Web検索 + RSSフィードからビジネス話題を自動取得するスクリプト

複数のソースから自動的にビジネス関連コンテンツを取得し、
成瀬さんのnote題材候補として提案する。

使い方:
  python fetch_business_topics.py                    # デフォルト: Web検索 + RSS統合
  python fetch_business_topics.py --web-only         # Web検索のみ
  python fetch_business_topics.py --rss-only         # RSSのみ
  python fetch_business_topics.py --output topics.json  # JSON出力
"""

import json
import sys
import io
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

# Windows環境でのUTF-8出力対応
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "auto_business_topics.json"

# 検索キーワード（成瀬さんのパーソナリティに基づく）
SEARCH_KEYWORDS = [
    "AI自動化",
    "Claude Code",
    "AI起業",
    "ビジネス変革",
    "経営戦略",
    "組織文化",
    "Antigravity",
    "個人開発",
]

# RSSフィードソース
RSS_FEEDS = {
    "TechCrunch Japan": "https://jp.techcrunch.com/feed/",
    "Hacker News": "https://news.ycombinator.com/rss",
    "Product Hunt": "https://www.producthunt.com/feed.xml",
}


class RSSParser(HTMLParser):
    """簡易RSSパーサー"""

    def __init__(self):
        super().__init__()
        self.in_item = False
        self.in_title = False
        self.in_link = False
        self.in_description = False
        self.in_pubdate = False
        self.current = {}
        self.items = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "item":
            self.in_item = True
            self.current = {}
        elif tag == "title" and self.in_item:
            self.in_title = True
        elif tag == "link" and self.in_item:
            self.in_link = True
        elif tag == "description" and self.in_item:
            self.in_description = True
        elif tag == "pubdate" and self.in_item:
            self.in_pubdate = True

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "item":
            self.in_item = False
            if self.current.get("title") and self.current.get("link"):
                self.items.append(self.current)
        elif tag == "title" and self.in_item:
            self.in_title = False
        elif tag == "link" and self.in_item:
            self.in_link = False
        elif tag == "description" and self.in_item:
            self.in_description = False
        elif tag == "pubdate" and self.in_item:
            self.in_pubdate = False

    def handle_data(self, data):
        if self.in_title:
            self.current["title"] = data.strip()
        elif self.in_link:
            self.current["link"] = data.strip()
        elif self.in_description:
            self.current["description"] = data.strip()[:200]
        elif self.in_pubdate:
            self.current["pubdate"] = data.strip()


def fetch_web_search_results(keyword, max_results=5):
    """Web検索でキーワード関連のコンテンツを取得（簡易版）"""
    results = []

    # 注：実際にはWebFetchツールを使用する予定
    # ここではスケルトンのみ提供
    print(f"  🔍 '{keyword}' を検索中...", file=sys.stderr)

    return results


def fetch_rss_feed(feed_url, feed_name):
    """RSSフィードから最新コンテンツを取得"""
    items = []

    try:
        print(f"  📡 {feed_name} から取得中...", file=sys.stderr)

        req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read().decode("utf-8")

        # XMLをパース
        root = ET.fromstring(xml_data)

        # RSS/Atomの両方に対応
        namespace = {
            'content': 'http://purl.org/rss/1.0/modules/content/',
            'atom': 'http://www.w3.org/2005/Atom'
        }

        for item in root.findall('.//item') + root.findall('.//atom:entry', namespace):
            title_elem = item.find('title') or item.find('atom:title', namespace)
            link_elem = item.find('link') or item.find('atom:link', namespace)
            desc_elem = item.find('description') or item.find('summary', namespace) or item.find('atom:summary', namespace)
            pubdate_elem = item.find('pubDate') or item.find('published', namespace)

            title = (title_elem.text or "").strip()
            link = (link_elem.text or link_elem.get('href') or "").strip()
            description = (desc_elem.text or "").strip()[:200]
            pubdate = (pubdate_elem.text or "").strip()

            if title and link:
                items.append({
                    "source": feed_name,
                    "title": title,
                    "description": description,
                    "link": link,
                    "pubdate": pubdate,
                    "type": "rss"
                })

        print(f"    ✓ {len(items)}件取得", file=sys.stderr)
        return items

    except Exception as e:
        print(f"    ✗ エラー: {e}", file=sys.stderr)
        return []


def aggregate_business_topics(web_results, rss_results):
    """複数ソースの結果を統合"""
    all_topics = []

    # Webタイプ
    for result in web_results:
        all_topics.append({
            **result,
            "type": "web_search",
            "retrieved_at": datetime.now().isoformat()
        })

    # RSSタイプ
    for result in rss_results:
        all_topics.append({
            **result,
            "retrieved_at": datetime.now().isoformat()
        })

    return all_topics


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ビジネス話題を自動取得")
    parser.add_argument("--web-only", action="store_true", help="Web検索のみ")
    parser.add_argument("--rss-only", action="store_true", help="RSSのみ")
    parser.add_argument("--output", default="", help="出力ファイル")
    args = parser.parse_args()

    print("📚 ビジネス話題を自動取得中...\n", file=sys.stderr)

    web_results = []
    rss_results = []

    # Web検索（RSSのみでない場合）
    if not args.rss_only:
        print("🌐 Web検索:", file=sys.stderr)
        for keyword in SEARCH_KEYWORDS[:3]:  # 最初の3つのみ実行
            results = fetch_web_search_results(keyword)
            web_results.extend(results)

    # RSS取得（Webのみでない場合）
    if not args.web_only:
        print("\n📰 RSSフィード:", file=sys.stderr)
        for feed_name, feed_url in RSS_FEEDS.items():
            results = fetch_rss_feed(feed_url, feed_name)
            rss_results.extend(results)

    # 統合
    all_topics = aggregate_business_topics(web_results, rss_results)

    # 出力
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "total_topics": len(all_topics),
        "sources": {
            "web_search": len(web_results),
            "rss": len(rss_results)
        },
        "topics": all_topics
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ {args.output} に保存しました", file=sys.stderr)
    else:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ {OUTPUT_PATH} に保存しました", file=sys.stderr)

    print(f"📊 取得サマリー:", file=sys.stderr)
    print(f"  - 総件数: {len(all_topics)}件", file=sys.stderr)
    print(f"  - Web検索: {len(web_results)}件", file=sys.stderr)
    print(f"  - RSSフィード: {len(rss_results)}件", file=sys.stderr)


if __name__ == "__main__":
    main()
