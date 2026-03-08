"""
X Bookmark Daily Digest - メインエントリポイント

パイプライン:
  1. 環境変数ロード
  2. bookmarks.json 読み込み
  3. 処理済みID除外（差分処理）
  4. Web検索でエンリッチメント（キーワード抽出 + DuckDuckGo）
  5. Claude API でバッチ要約・カテゴリ分け
  6. DigestResult 組み立て
  7. Slack 通知
  8. 処理済みID保存
"""

import os
import sys
import json
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from .bookmark_loader import (
    load_bookmarks,
    load_processed_ids,
    save_processed_ids,
    filter_new_bookmarks,
)
from .search_enricher import enrich_all_bookmarks
from .summarizer import build_enriched_bookmarks
from .slack_notifier import send_to_slack, send_error_to_slack
from .models import DigestResult
from .utils import get_logger

logger = get_logger(__name__)
JST = timezone(timedelta(hours=9))

# デフォルトのブックマークファイルパス
BOOKMARKS_FILE = os.environ.get("BOOKMARKS_FILE", "data/bookmarks.json")
PROCESSED_IDS_FILE = os.environ.get("PROCESSED_IDS_FILE", "data/processed_ids.json")


def load_env(dry_run: bool = False) -> dict[str, str]:
    """
    環境変数を読み込む。
    .env ファイルがあれば優先的に読み込む（ローカル開発用）。
    """
    # .env ファイルの読み込み（存在する場合のみ）
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(".env ファイルを読み込みました")

    required_keys = [
        "ANTHROPIC_API_KEY",
    ]
    if not dry_run:
        required_keys.append("SLACK_WEBHOOK_URL")
        
    env: dict[str, str] = {}
    missing: list[str] = []

    for key in required_keys:
        val = os.environ.get(key, "").strip()
        if not val:
            missing.append(key)
        else:
            env[key] = val

    if missing:
        raise EnvironmentError(
            f"以下の環境変数が設定されていません: {', '.join(missing)}\n"
            f".env.example を参考に .env ファイルを作成してください。"
        )

    return env


def run_digest(
    bookmarks_file: str = BOOKMARKS_FILE,
    processed_ids_file: str = PROCESSED_IDS_FILE,
    dry_run: bool = False,
    max_items: int = 30,
    skip_enrich: bool = False,
) -> None:
    """
    メインパイプラインを実行する。

    Args:
        bookmarks_file: ブックマーク JSON/CSV ファイルのパス
        processed_ids_file: 処理済み ID キャッシュファイルのパス
        dry_run: True の場合 Slack 送信をスキップ（テスト用）
    """
    now = datetime.now(JST)
    logger.info(f"=== X Bookmark Digest 開始: {now.strftime('%Y-%m-%d %H:%M JST')} ===")

    # --- 環境変数ロード ---
    env = load_env(dry_run=dry_run)
    slack_webhook_url = env.get("SLACK_WEBHOOK_URL", "")
    anthropic_api_key = env["ANTHROPIC_API_KEY"]

    try:
        # --- 1. ブックマーク読み込み ---
        logger.info(f"ブックマークファイルを読み込みます: {bookmarks_file}")
        all_bookmarks = load_bookmarks(bookmarks_file)

        # --- 2. 差分処理（処理済みをスキップ）---
        processed_ids = load_processed_ids(processed_ids_file)
        bookmarks = filter_new_bookmarks(all_bookmarks, processed_ids)

        if not bookmarks:
            logger.info("新規ブックマークがありません。処理を終了します。")
            sys.exit(0)

        # 上限件数に切り詰め（新しい順に max_items 件のみ処理）
        if len(bookmarks) > max_items:
            logger.info(f"{len(bookmarks)} 件中、直近 {max_items} 件のみ処理します")
            bookmarks = bookmarks[:max_items]

        logger.info(f"新規ブックマーク {len(bookmarks)} 件を処理します")

        # --- 3. Anthropic クライアント初期化 ---
        anthropic_client = Anthropic(api_key=anthropic_api_key)

        # --- 4. Web検索エンリッチメント ---
        if skip_enrich:
            logger.info("エンリッチメントをスキップします (--skip-enrich)")
            enrichment_data = {bm.id: ([], []) for bm in bookmarks}
        else:
            logger.info("Web検索でエンリッチメントを開始します...")
            enrichment_data = enrich_all_bookmarks(anthropic_client, bookmarks)

        # --- 5. 要約・カテゴリ分け ---
        logger.info("Claude API で要約・カテゴリ分けを開始します...")
        enriched_bookmarks, token_usage = build_enriched_bookmarks(
            anthropic_client, bookmarks, enrichment_data
        )

        # --- 6. DigestResult 組み立て ---
        result = DigestResult(
            date=now,
            bookmarks=enriched_bookmarks,
            total_count=len(enriched_bookmarks),
            model_used="claude-sonnet-4-5 / claude-haiku-4-5",
            token_usage=token_usage,
        )

        # --- 7. Slack 通知 ---
        if dry_run:
            logger.info("[DRY RUN] Slack 送信をスキップします")
            _print_digest_summary(result)
        else:
            logger.info("Slack に送信します...")
            send_to_slack(slack_webhook_url, result)

        # --- 8. ダイジェストキャッシュ保存（Slack Bot 用）---
        _save_digest_cache(result)

        # --- 9. 処理済みID保存 ---
        new_ids = {bm.bookmark.id for bm in enriched_bookmarks}
        save_processed_ids(new_ids, processed_ids_file)

        logger.info(f"=== X Bookmark Digest 完了 ===")

    except FileNotFoundError as e:
        logger.error(str(e))
        send_error_to_slack(slack_webhook_url, str(e))
        sys.exit(1)

    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(f"予期しないエラーが発生しました:\n{error_detail}")
        send_error_to_slack(slack_webhook_url, f"{type(e).__name__}: {e}")
        sys.exit(1)


def _save_digest_cache(result: DigestResult) -> None:
    """Slack Bot が参照できるようダイジェスト内容をJSONファイルに保存する"""
    cache_file = os.environ.get("DIGEST_CACHE_FILE", "data/digest_cache.json")
    data = {
        "date": result.date.strftime("%Y-%m-%d"),
        "total_count": result.total_count,
        "bookmarks": [
            {
                "id": bm.bookmark.id,
                "author_username": bm.bookmark.author_username,
                "author_display_name": bm.bookmark.author_name,
                "text": bm.bookmark.text,
                "url": bm.bookmark.url,
                "like_count": bm.bookmark.like_count,
                "category": bm.category,
                "summary": bm.summary,
                "importance": bm.importance,
                "keywords": bm.keywords,
                "enrichment_summary": bm.enrichment_summary,
                "web_results": [
                    {"title": r.title, "url": r.url, "snippet": r.snippet}
                    for r in bm.web_results
                ],
            }
            for bm in result.bookmarks
        ],
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"ダイジェストキャッシュを保存しました: {cache_file}")


def _print_digest_summary(result: DigestResult) -> None:
    """ダイジェスト内容をコンソールに出力する（dry_run 用）"""
    print("\n" + "=" * 60)
    print(f"📚 X Bookmark Digest ({result.date.strftime('%Y/%m/%d')})")
    print(f"合計: {result.total_count} 件")
    print("=" * 60)
    for bm in result.bookmarks:
        print(f"\n[{bm.category}] @{bm.bookmark.author_username}")
        print(f"  要約: {bm.summary}")
        if bm.enrichment_summary:
            print(f"  補足: {bm.enrichment_summary}")
        if bm.keywords:
            print(f"  KW: {', '.join(bm.keywords)}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="X Bookmark Daily Digest")
    parser.add_argument(
        "--bookmarks",
        default=BOOKMARKS_FILE,
        help=f"ブックマークファイルパス (default: {BOOKMARKS_FILE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Slack 送信をスキップしてコンソールに出力のみ",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="処理済みIDキャッシュを無視して全件処理",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=int(os.environ.get("MAX_ITEMS", "30")),
        help="1回の実行で処理するブックマークの最大件数 (default: 30)",
    )
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        default=os.environ.get("SKIP_ENRICH", "").lower() in ("1", "true"),
        help="Web検索エンリッチメントをスキップして高速化",
    )
    args = parser.parse_args()

    # --no-cache の場合は空のキャッシュファイルとして扱う
    proc_file = PROCESSED_IDS_FILE
    if args.no_cache:
        logger.info("--no-cache: 処理済みIDキャッシュを無視します")
        proc_file = "__no_cache__"  # 存在しないファイルを指定 = 空セットになる

    run_digest(
        bookmarks_file=args.bookmarks,
        processed_ids_file=proc_file,
        dry_run=args.dry_run,
        max_items=args.max_items,
        skip_enrich=args.skip_enrich,
    )
