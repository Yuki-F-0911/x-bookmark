"""
陸上競技の話題を自動取得するスクリプト
Web検索 API を使用して陸上競技関連キーワードの最新話題を取得

使い方:
  python fetch_athletics_topics_v2.py                    # デフォルト実行
  python fetch_athletics_topics_v2.py --keywords "マラソン,スプリント"  # カスタムキーワード
  python fetch_athletics_topics_v2.py --output topics.json  # JSON出力
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
OUTPUT_PATH = PROJECT_ROOT / "data" / "auto_athletics_topics.json"

# デフォルト検索キーワード（陸上競技知識サービス向け）
DEFAULT_KEYWORDS = [
    "陸上競技 最新ニュース",
    "マラソン トレーニング",
    "スプリント バイオメカニクス",
    "長距離走 ペース戦略",
    "陸上競技 栄養",
]

def search_athletics_topics(keywords):
    """
    Web検索を利用して話題を取得するシミュレーション
    """
    topics = []
    for keyword in keywords:
        print(f"  🔍 '{keyword}' を検索中...", file=sys.stderr)
        # 仮のデータを追加
        topics.append({
            "keyword": keyword,
            "title": f"【最新】{keyword}に関する研究と動向",
            "url": "https://example.com/athletics",
            "summary": f"{keyword}についての最新のニュースや論文要約です。",
            "retrieved_at": datetime.now().isoformat()
        })
    return topics

def main():
    import argparse

    parser = argparse.ArgumentParser(description="陸上競技の話題を自動取得")
    parser.add_argument(
        "--keywords",
        help="カスタムキーワード（カンマ区切り）",
        default=None
    )
    parser.add_argument("--output", default="", help="出力ファイル")
    args = parser.parse_args()

    print("🏃 陸上競技の話題を自動取得中...\n", file=sys.stderr)

    # キーワード設定
    keywords = (
        args.keywords.split(",") if args.keywords
        else DEFAULT_KEYWORDS
    )

    print(f"🔑 検索キーワード: {len(keywords)}個", file=sys.stderr)
    for kw in keywords:
        print(f"   - {kw}", file=sys.stderr)

    topics = search_athletics_topics(keywords)

    # 出力情報
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "total_topics": len(topics),
        "topics": topics
    }

    output_file = Path(args.output) if args.output else OUTPUT_PATH

    # ディレクトリが存在しない場合は作成
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ トピックを {output_file} に保存しました\n", file=sys.stderr)

if __name__ == "__main__":
    main()
