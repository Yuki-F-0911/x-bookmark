#!/usr/bin/env python3
"""
ニュースレター記事自動生成スクリプト

digest_cache.json → Claude APIで洗練された記事に変換 → Markdown出力
Note / Substack にそのまま投稿可能な形式で出力する。

使い方:
  python generate_newsletter.py                          # 記事生成（標準出力）
  python generate_newsletter.py --output newsletter.md   # ファイル出力
  python generate_newsletter.py --format note            # Note向けフォーマット
  python generate_newsletter.py --format substack        # Substack向けフォーマット
  python generate_newsletter.py --no-ai                  # Claude API不使用（テンプレのみ）
"""

import json
import sys
import io
import os
import argparse
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
DIGEST_CACHE = PROJECT_ROOT / "data" / "digest_cache.json"
OUTPUT_DIR = PROJECT_ROOT / "newsletters"

# ニュースレターのブランド設定
NEWSLETTER_CONFIG = {
    "name": "AI×SaaS Weekly Insight",
    "tagline": "起業家とエンジニアのための生成AI・SaaS最前線",
    "author": "Yuki Futami",
    "footer": "AI×SaaS Weekly Insight｜毎日のXブックマークから厳選した最新トレンドをお届け",
}

ARTICLE_PROMPT = """あなたはテック系有料ニュースレター「{name}」の編集長です。
以下のブックマーク分析データから、起業家・エンジニア向けの高品質なニュースレター記事を生成してください。

## 記事要件
- 読者: AI/SaaS領域の起業家、プロダクトマネージャー、エンジニア
- トーン: 専門的だが親しみやすい。「へえ、そうなんだ」と思わせるインサイト重視
- 構成: 下記テンプレートに従う
- 文字数: 2000〜3000字

## 記事テンプレート

### 冒頭（リード文）
今日の注目テーマを1〜2文で端的に示す。読者の関心を引くフックを入れる。

### 🔥 今日のトップ3
重要度"high"の記事から最も注目すべき3つをピックアップ。
各トピックについて:
- 何が起きているか（事実）
- なぜ重要か（インサイト）
- 読者が取るべきアクション（示唆）
を3〜5文で簡潔に解説。

### 📊 トレンドウォッチ
通常記事から見えるマクロトレンドを2〜3個抽出。
「点」ではなく「線」で捉えた分析を提供。

### 💡 編集部の視点
全体を俯瞰した独自の考察を1段落で。
「この動きが意味すること」「半年後どうなるか」の示唆。

### 📎 今日のリンク集
全記事のリンクをカテゴリ別にまとめる。

---

## ブックマークデータ
{bookmarks_json}

## 出力形式
Markdown形式で記事本文のみを出力してください。メタ情報や指示への返答は不要です。
"""

NOTE_HEADER = """---
title: "{title}"
emoji: "🤖"
type: "tech"
topics: ["AI", "SaaS", "生成AI", "ニュースレター"]
published: false
---

"""

SUBSTACK_HEADER = """---
title: "{title}"
subtitle: "{subtitle}"
---

"""


def load_digest_cache(path: Path = DIGEST_CACHE) -> dict:
    if not path.exists():
        print(f"[ERROR] digest_cache.json が見つかりません: {path}", file=sys.stderr)
        print("先に python -m src.main を実行してダイジェストを生成してください。", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_with_ai(digest_data: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY が設定されていません", file=sys.stderr)
        sys.exit(1)

    client = Anthropic(api_key=api_key)

    # high/normalのみ抽出してトークン節約
    relevant = [
        bm for bm in digest_data.get("bookmarks", [])
        if bm.get("importance") != "low"
    ]
    bookmarks_json = json.dumps(relevant, ensure_ascii=False, indent=2)

    prompt = ARTICLE_PROMPT.format(
        name=NEWSLETTER_CONFIG["name"],
        bookmarks_json=bookmarks_json,
    )

    print("[INFO] Claude APIで記事を生成中...", file=sys.stderr)
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


def generate_template_only(digest_data: dict) -> str:
    """AI不使用のテンプレートベース生成"""
    date_str = digest_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    bookmarks = digest_data.get("bookmarks", [])

    high = [b for b in bookmarks if b.get("importance") == "high"]
    normal = [b for b in bookmarks if b.get("importance") == "normal"]

    lines = [
        f"# {NEWSLETTER_CONFIG['name']}｜{date_str}",
        f"\n> {NEWSLETTER_CONFIG['tagline']}\n",
    ]

    if high:
        lines.append("## 🔥 今日のトップピックアップ\n")
        for bm in high[:5]:
            author = bm.get("author_username", "unknown")
            summary = bm.get("summary", "")
            url = bm.get("url", "")
            category = bm.get("category", "")
            lines.append(f"### [{category}] @{author}")
            lines.append(f"{summary}\n")
            if bm.get("enrichment_summary"):
                lines.append(f"> 💡 {bm['enrichment_summary']}\n")
            lines.append(f"[元ツイートを見る]({url})\n")

    if normal:
        # カテゴリ別に整理
        by_cat: dict[str, list] = {}
        for bm in normal:
            cat = bm.get("category", "その他")
            by_cat.setdefault(cat, []).append(bm)

        lines.append("## 📊 カテゴリ別まとめ\n")
        for cat, bms in sorted(by_cat.items(), key=lambda x: len(x[1]), reverse=True):
            lines.append(f"### {cat}\n")
            for bm in bms[:5]:
                author = bm.get("author_username", "unknown")
                summary = bm.get("summary", "")
                url = bm.get("url", "")
                lines.append(f"- **@{author}**: {summary} [→]({url})")
            lines.append("")

    lines.append(f"\n---\n_{NEWSLETTER_CONFIG['footer']}_\n")
    return "\n".join(lines)


def format_output(article: str, fmt: str, digest_data: dict) -> str:
    date_str = digest_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    title = f"{NEWSLETTER_CONFIG['name']}｜{date_str}"

    if fmt == "note":
        header = NOTE_HEADER.format(title=title)
        return header + article
    elif fmt == "substack":
        header = SUBSTACK_HEADER.format(
            title=title,
            subtitle=NEWSLETTER_CONFIG["tagline"],
        )
        return header + article
    return article


def main():
    parser = argparse.ArgumentParser(description="ニュースレター記事自動生成")
    parser.add_argument("--output", "-o", help="出力ファイルパス")
    parser.add_argument("--format", "-f", choices=["plain", "note", "substack"],
                        default="plain", help="出力フォーマット")
    parser.add_argument("--no-ai", action="store_true",
                        help="Claude API不使用（テンプレートのみ）")
    parser.add_argument("--cache", default=str(DIGEST_CACHE),
                        help="ダイジェストキャッシュファイルパス")
    args = parser.parse_args()

    digest_data = load_digest_cache(Path(args.cache))
    print(f"[INFO] {digest_data.get('total_count', 0)}件のブックマークを読み込みました", file=sys.stderr)

    if args.no_ai:
        article = generate_template_only(digest_data)
    else:
        article = generate_with_ai(digest_data)

    output = format_output(article, args.format, digest_data)

    if args.output:
        OUTPUT_DIR.mkdir(exist_ok=True)
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = OUTPUT_DIR / out_path
        out_path.write_text(output, encoding="utf-8")
        print(f"[OK] 記事を保存しました: {out_path}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
