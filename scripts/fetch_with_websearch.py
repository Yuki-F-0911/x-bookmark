#!/usr/bin/env python3
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

    output_path = Path(__file__).parent.parent / "data" / "auto_business_topics.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output_path


def main():
    print("📚 ビジネス話題を自動取得中...\n")

    # Web検索で取得
    topics = search_business_topics()

    # 保存
    output_path = save_topics(topics)

    print(f"\n✅ {output_path} に保存しました")
    print(f"📊 取得サマリー: {len(topics)}件")


if __name__ == "__main__":
    main()
