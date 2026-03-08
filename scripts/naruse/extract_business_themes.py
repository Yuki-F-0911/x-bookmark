"""
Xブックマークからビジネス関連の題材を自動抽出し、成瀬さんのnote記事案として提案するスクリプト

使い方:
  python extract_business_themes.py                    # 最新30件を取得
  python extract_business_themes.py --limit 50        # 最新50件を取得
  python extract_business_themes.py --output themes.md # Markdown出力
"""

import json
import sys
import io
from pathlib import Path
from datetime import datetime

# Windows環境でのUTF-8出力対応
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent.parent.parent
BOOKMARKS_PATH = PROJECT_ROOT / "data" / "bookmarks.json"
NARUSE_THEMES_PATH = PROJECT_ROOT.parent / "WillForward" / "PersonalizeData" / "naruse" / "note_themes"


# ビジネステーマのカテゴリマッピング
THEME_CATEGORIES = {
    "AI×経営": ["AI", "自動化", "Claude", "Gemini", "エージェント", "プロンプト", "LLM"],
    "個人起業・副業": ["月10万", "起業", "副業", "フリーランス", "個人開発", "マネタイズ"],
    "組織・チームビルディング": ["組織文化", "チームワーク", "リーダーシップ", "人材育成", "採用"],
    "教育・スキルアップ": ["スキル", "学習", "研修", "資格", "教育"],
    "マーケティング・SNS": ["マーケティング", "SNS", "ブランディング", "コンテンツ", "フォロワー"],
    "経営戦略・ビジョン": ["ビジョン", "戦略", "経営", "ビジネスモデル", "成長"],
    "スタートアップ・資金": ["資金調達", "スタートアップ", "投資", "VC", "シード"],
}

# 成瀬さんのパーソナリティに高合致するキーワード（重み付け）
# 【成瀬さんが似合う題材】
# - 社会変革・パラダイムシフト（AIが社会をどう変えるか）
# - 人間観の変化（AIとの共存による人の役割の再定義）
# - 組織論・経営戦略（個・組織・社会の三位一体）
# - 思想・ビジョン（Will Out、世界を一つの家族に）
NARUSE_AFFINITY_KEYWORDS = {
    # 【最高優先度】パラダイム・社会変革系
    "パラダイムシフト": 4,
    "時代の転換": 4,
    "社会変革": 4,
    "AIが社会を変える": 4,
    "新しい時代": 4,

    # 【高優先度】人間観・仕事観の変化
    "人間の役割": 3.5,
    "仕事観": 3.5,
    "人生観": 3.5,
    "働き方の変化": 3.5,
    "人生の意味": 3.5,

    # コア概念
    "Will Out": 3,
    "世界を一つの家族": 3,
    "仕組み": 3,
    "協働": 2.5,

    # ビジョン・価値観
    "挑戦": 2,
    "応援": 2,
    "ほっこり": 2.5,
    "影響力": 2,
    "個・組織・社会": 2,
    "意志": 1.5,
    "仲間": 1.5,
    "ビジョン": 1.5,

    # ビジネス戦略・組織論
    "組織文化": 2.5,
    "リーダーシップ": 2,
    "人材育成": 2,
    "経営戦略": 2,

    # ビジネス視点（低め）
    "AI": 0.5,
    "変化": 0.5,
    "成長": 0.5,
    "時代": 0.5,

    # 教育・学習
    "教育": 1,
    "コンサルティング": 1,
    "起業": 0.5,
}

# 【ペナルティ】成瀬さんに不向きなキーワード（軽減版）
# ツール活用・ハウツー系は減点するが、完全に排除しない
# 重要：複合的なテーマ（例：「AI自動化が人の仕事観を変える」）なら加点される
NARUSE_PENALTY_KEYWORDS = {
    # 稼ぎ方・ハウツー系（強ペナルティ）
    "月10万": -1.5,
    "月30万": -1.5,
    "稼ぎ方": -1.5,
    "マネタイズ": -1.5,
    "収益モデル": -1,
    "完全自動化": -1,

    # 短期的SNS・マーケティング系
    "フォロワー": -1,
    "バズ": -1,

    # 個人開発・テクニック系（軽めのペナルティ）
    "プロンプト": -0.5,
    "コード": -0.5,
    "実装手順": -0.5,
}

# テーマ別の親和度ボーナス（調整版）
THEME_AFFINITY_BONUS = {
    "経営戦略・ビジョン": 3.0,  # 大幅アップ：成瀬さんの中心
    "組織・チームビルディング": 2.5,  # アップ
    "教育・スキルアップ": 1.5,
    "AI×経営": 0.5,  # わずかなボーナス（ハウツー系が多いが）
    "個人起業・副業": -0.5,  # 軽いペナルティ
    "マーケティング・SNS": -1.0,  # 中程度のペナルティ
    "スタートアップ・資金": 1.0,  # むしろポジティブ
}


def load_bookmarks(limit=30):
    """bookmarks.jsonを読み込む"""
    if not BOOKMARKS_PATH.exists():
        print(f"エラー: {BOOKMARKS_PATH} が見つかりません", file=sys.stderr)
        return []

    try:
        with open(BOOKMARKS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data[:limit]
    except json.JSONDecodeError as e:
        print(f"JSON解析エラー: {e}", file=sys.stderr)
        return []


def classify_theme(text):
    """テキストからビジネステーマを分類"""
    text_lower = text.lower()
    matched_categories = []

    for category, keywords in THEME_CATEGORIES.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                matched_categories.append(category)
                break

    return matched_categories if matched_categories else ["その他"]


def calculate_naruse_affinity(text, categories):
    """
    成瀬さんのパーソナリティとの親和度スコアを計算（0-10）

    【成瀬さんが似合う題材】
    - 社会変革・パラダイムシフト（AIが社会をどう変えるか）
    - 人間観の変化（AIとの共存による人の役割の再定義）
    - 組織論・経営戦略（個・組織・社会の三位一体）

    【不向きな題材】
    - AIツール活用・実装ガイド（稼ぎ方、自動化テクニック）
    - SNS・マーケティング戦術
    """
    score = 2.0  # ベーススコア

    text_lower = text.lower()

    # 親和度キーワード加算
    for keyword, weight in NARUSE_AFFINITY_KEYWORDS.items():
        if keyword.lower() in text_lower:
            score += weight

    # ペナルティキーワード減算
    for keyword, penalty in NARUSE_PENALTY_KEYWORDS.items():
        if keyword.lower() in text_lower:
            score += penalty  # penalty は負数なので減算される

    # テーマボーナス
    for category in categories:
        if category in THEME_AFFINITY_BONUS:
            score += THEME_AFFINITY_BONUS[category]

    # スコアの正規化
    # 最小0、最大10にクリップ
    return max(0.0, min(score, 10.0))


def extract_business_themes(bookmarks):
    """ブックマークからビジネステーマを抽出"""
    themes = []

    for idx, bookmark in enumerate(bookmarks, 1):
        text = bookmark.get("text", "")
        title = bookmark.get("article_title", "")
        author = bookmark.get("author_name", "")
        username = bookmark.get("author_username", "")
        url = bookmark.get("url", "")
        created_at = bookmark.get("created_at", "")

        # テーマを分類
        categories = classify_theme(text + " " + title)

        # 親和度スコア計算
        affinity = calculate_naruse_affinity(text + " " + title, categories)

        # 内容を集約
        summary = title if title else text[:100].strip()

        themes.append({
            "id": idx,
            "title": title or text[:50],
            "summary": summary,
            "categories": categories,
            "affinity_score": affinity,
            "author": author,
            "username": username,
            "url": url,
            "created_at": created_at,
        })

    return themes


def format_markdown_themes(themes):
    """テーマをMarkdown形式で整形"""
    # 親和度スコア順でソート（高い順）
    sorted_themes = sorted(themes, key=lambda x: x["affinity_score"], reverse=True)

    output = f"""# 成瀬さんのnote題材候補 - {datetime.now().strftime('%Y年%m月%d日')}

> このドキュメントは、X Bookmark Digestから自動抽出したビジネス関連テーマのうち、成瀬さんのパーソナリティに高合致するものを提案しています。
> **親和度スコア** が高いほど、成瀬さんのnote記事として書きやすい題材です。

---

## 📊 統計

- 取得ツイート: {len(themes)}件
- 平均親和度スコア: {sum(t["affinity_score"] for t in themes) / len(themes):.2f}/10
- **高親和度（7以上）**: {len([t for t in sorted_themes if t["affinity_score"] >= 7])}件
- **中親和度（5-7）**: {len([t for t in sorted_themes if 5 <= t["affinity_score"] < 7])}件

---

## 🎯 高親和度の題材（7以上）

"""

    high_affinity = [t for t in sorted_themes if t["affinity_score"] >= 7]
    for theme in high_affinity:
        output += f"""### {theme["id"]}. {theme["title"][:50]}... ⭐{theme["affinity_score"]:.1f}/10

**テーマ**: {' / '.join(theme["categories"])}

**概要**
{theme["summary"][:200]}

**ソース**: [@{theme["username"]}]({theme["url"]}) - {theme["author"]}

---

"""

    output += f"""
## 💡 中親和度の題材（5-7）

"""

    mid_affinity = [t for t in sorted_themes if 5 <= t["affinity_score"] < 7]
    for theme in mid_affinity:
        output += f"""### {theme["id"]}. {theme["title"][:50]}... ⭐{theme["affinity_score"]:.1f}/10
- **テーマ**: {' / '.join(theme["categories"])}
- **ソース**: [@{theme["username"]}]({theme["url"]})

"""

    output += f"""
## 📌 参考（低親和度）

"""

    low_affinity = [t for t in sorted_themes if t["affinity_score"] < 5]
    for theme in low_affinity:
        output += f"""- {theme["title"][:60]}... ({' / '.join(theme["categories"])}) ⭐{theme["affinity_score"]:.1f}/10

"""

    return output


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Xブックマークからビジネステーマを抽出")
    parser.add_argument("--limit", type=int, default=30, help="取得件数（デフォルト30）")
    parser.add_argument("--output", default="", help="出力ファイル（デフォルト: 表示のみ）")
    args = parser.parse_args()

    # ブックマークを読み込む
    print(f"📚 {args.limit}件のブックマークを読み込み中...\n", file=sys.stderr)
    bookmarks = load_bookmarks(args.limit)

    if not bookmarks:
        print("ブックマークが見つかりません", file=sys.stderr)
        sys.exit(1)

    # テーマを抽出
    print(f"🔍 ビジネステーマを分類中...\n", file=sys.stderr)
    themes = extract_business_themes(bookmarks)

    # Markdown形式で整形
    markdown_output = format_markdown_themes(themes)

    # 出力
    if args.output:
        # ファイル出力
        NARUSE_THEMES_PATH.mkdir(parents=True, exist_ok=True)
        output_file = NARUSE_THEMES_PATH / args.output
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown_output)
        print(f"✅ {output_file} に保存しました", file=sys.stderr)
    else:
        # コンソール出力
        print(markdown_output)


if __name__ == "__main__":
    main()
