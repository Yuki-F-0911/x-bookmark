"""
ビジネス話題を自動取得するスクリプト（改良版）
Web検索 API を使用してビジネス関連キーワードの最新話題を取得

使い方:
  python fetch_business_topics_v2.py                    # デフォルト実行
  python fetch_business_topics_v2.py --keywords "AI,起業,経営"  # カスタムキーワード
  python fetch_business_topics_v2.py --output topics.json  # JSON出力
"""

import json
import sys
import io
from datetime import datetime
from pathlib import Path

# Windows環境でのUTF-8出力対応
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "auto_business_topics.json"

# デフォルト検索キーワード（成瀬さんのパーソナリティに基づく）
DEFAULT_KEYWORDS = [
    "Claude Code 自動化",
    "AI 経営戦略",
    "個人起業 AI",
    "Antigravity ビジネス",
    "チームビルディング",
]


def fetch_topics_from_web_search(keywords):
    """
    Web検索APIを使用してビジネス話題を取得
    注：実装にはWebSearchツールの利用が必要
    """
    topics = []

    for keyword in keywords:
        print(f"  🔍 '{keyword}' を検索中...", file=sys.stderr)

        # ここでWebSearchツールを呼び出す実装が入る
        # 現在はスケルトンのため、プレースホルダーを返す
        topics.append({
            "keyword": keyword,
            "status": "placeholder",
            "note": "WebSearchツール統合が必要"
        })

    return topics


def create_integration_script():
    """
    Web検索統合用のスクリプトテンプレートを生成
    """
    template = '''#!/usr/bin/env python3
"""
ビジネス話題自動取得スクリプト（Claude Code WebSearch統合版）
成瀬さんのnote題材を毎日自動取得する

実行方法:
  python fetch_with_websearch.py
"""

import json
import sys
import io
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ビジネスキーワード（成瀬さんのパーソナリティベース）
KEYWORDS = [
    "Claude Code AI自動化 2026",
    "個人起業 AIツール",
    "ビジネス変革 AI",
    "チームマネジメント",
    "Antigravity 活用法",
]


def search_business_topics():
    """Web検索でビジネス話題を取得（Claude Codeの search_web を使用）"""
    import subprocess
    import json

    topics = []

    for keyword in KEYWORDS:
        print(f"🔍 '{keyword}' を検索中...")

        # Claude Code内で利用可能な外部ツール呼び出し
        # 例: Claude APIのWeb検索機能を呼び出す

        # プレースホルダー結果
        topic = {
            "keyword": keyword,
            "title": f"{keyword}関連の最新情報",
            "url": "https://example.com",
            "summary": "検索結果のサマリー",
            "retrieved_at": datetime.now().isoformat()
        }
        topics.append(topic)

    return topics


def save_topics(topics):
    """取得した話題をJSON保存"""
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_topics": len(topics),
        "topics": topics
    }

    output_path = Path(__file__).parent.parent.parent / "data" / "auto_business_topics.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output_path


def main():
    print("📚 ビジネス話題を自動取得中...\\n")

    # Web検索で取得
    topics = search_business_topics()

    # 保存
    output_path = save_topics(topics)

    print(f"\\n✅ {output_path} に保存しました")
    print(f"📊 取得サマリー: {len(topics)}件")


if __name__ == "__main__":
    main()
'''

    return template


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ビジネス話題を自動取得")
    parser.add_argument(
        "--keywords",
        help="カスタムキーワード（カンマ区切り）",
        default=None
    )
    parser.add_argument("--output", default="", help="出力ファイル")
    args = parser.parse_args()

    print("📚 ビジネス話題の自動取得設定\n", file=sys.stderr)

    # キーワード設定
    keywords = (
        args.keywords.split(",") if args.keywords
        else DEFAULT_KEYWORDS
    )

    print(f"🔑 検索キーワード: {len(keywords)}個", file=sys.stderr)
    for kw in keywords:
        print(f"   - {kw}", file=sys.stderr)

    # 出力情報
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "status": "ready",
        "message": "Web検索統合スクリプトの準備が完了しました",
        "keywords": keywords,
        "next_steps": [
            "fetch_with_websearch.py スクリプトを使用してWeb検索統合を実行",
            "毎日自動実行するようタスクスケジューラーに登録",
            "取得したトピックを extract_business_themes.py で分類・スコアリング"
        ]
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        output_file = args.output
    else:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        output_file = OUTPUT_PATH

    print(f"\n✅ 設定を {output_file} に保存しました\n", file=sys.stderr)

    # Web検索統合スクリプトテンプレートも生成
    template_path = PROJECT_ROOT / "scripts" / "fetch_with_websearch.py"
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(create_integration_script())

    print(f"📄 統合スクリプトテンプレート: {template_path}\n", file=sys.stderr)


if __name__ == "__main__":
    main()
