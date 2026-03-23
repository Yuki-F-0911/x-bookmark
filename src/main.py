"""
X Bookmark Daily Digest - メインエントリポイント

パイプライン:
  1. 環境変数ロード
  2. bookmarks.json 読み込み
  3. 処理済みID除外（差分処理）
  4. Slack 通知
  5. 処理済みID保存
"""

import os
import sys
import json
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

from .bookmark_loader import (
    load_bookmarks,
    load_processed_ids,
    save_processed_ids,
    filter_new_bookmarks,
)
from .slack_notifier import send_to_slack, send_error_to_slack
from .utils import get_logger

logger = get_logger(__name__)
JST = timezone(timedelta(hours=9))

BOOKMARKS_FILE = os.environ.get("BOOKMARKS_FILE", "data/bookmarks.json")
PROCESSED_IDS_FILE = os.environ.get("PROCESSED_IDS_FILE", "data/processed_ids.json")


def load_env(dry_run: bool = False) -> dict[str, str]:
    """環境変数を読み込む"""
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(".env ファイルを読み込みました")

    required_keys: list[str] = []
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
    latest_mode: bool = False,
) -> None:
    """
    メインパイプラインを実行する。

    Args:
        bookmarks_file: ブックマーク JSON/CSV ファイルのパス
        processed_ids_file: 処理済み ID キャッシュファイルのパス
        dry_run: True の場合 Slack 送信をスキップ（テスト用）
        latest_mode: True の場合、processed_ids を無視して最新 max_items 件を常に送信
    """
    now = datetime.now(JST)
    logger.info(f"=== X Bookmark Digest 開始: {now.strftime('%Y-%m-%d %H:%M JST')} ===")

    env = load_env(dry_run=dry_run)
    slack_webhook_url = env.get("SLACK_WEBHOOK_URL", "")

    try:
        # --- 1. ブックマーク読み込み ---
        logger.info(f"ブックマークファイルを読み込みます: {bookmarks_file}")
        all_bookmarks = load_bookmarks(bookmarks_file)

        # --- 2. ブックマーク選択 ---
        if latest_mode:
            bookmarks = sorted(
                all_bookmarks,
                key=lambda bm: bm.created_at or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )[:max_items]
            # 前回と同じセットなら送信スキップ
            current_ids = {bm.id for bm in bookmarks}
            cache_file = os.environ.get("DIGEST_CACHE_FILE", "data/digest_cache.json")
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                cached_ids = set(cache.get("ids", []))
                if current_ids == cached_ids:
                    logger.info("最新30件に変化なし。送信をスキップします。")
                    sys.exit(0)
            logger.info(f"最新モード: {len(bookmarks)} 件を処理します")
        else:
            processed_ids = load_processed_ids(processed_ids_file)
            bookmarks = filter_new_bookmarks(all_bookmarks, processed_ids)

            if not bookmarks:
                logger.info("新規ブックマークがありません。処理を終了します。")
                sys.exit(0)

            if len(bookmarks) > max_items:
                logger.info(f"{len(bookmarks)} 件中、直近 {max_items} 件のみ処理します")
                bookmarks = bookmarks[:max_items]

        logger.info(f"ブックマーク {len(bookmarks)} 件を処理します")

        # --- 3. Slack 通知 ---
        if dry_run:
            logger.info("[DRY RUN] Slack 送信をスキップします")
            _print_bookmarks(bookmarks)
        else:
            logger.info("Slack に送信します...")
            send_to_slack(slack_webhook_url, bookmarks, now)

        # --- 4. キャッシュ保存 ---
        _save_cache(bookmarks)

        # --- 5. 処理済みID保存 ---
        new_ids = {bm.id for bm in bookmarks}
        save_processed_ids(new_ids, processed_ids_file)

        logger.info("=== X Bookmark Digest 完了 ===")

    except FileNotFoundError as e:
        logger.error(str(e))
        send_error_to_slack(slack_webhook_url, str(e))
        sys.exit(1)

    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(f"予期しないエラーが発生しました:\n{error_detail}")
        send_error_to_slack(slack_webhook_url, f"{type(e).__name__}: {e}")
        sys.exit(1)


def _save_cache(bookmarks: list) -> None:
    """latest モードの重複チェック用キャッシュを保存する"""
    cache_file = os.environ.get("DIGEST_CACHE_FILE", "data/digest_cache.json")
    data = {"ids": [bm.id for bm in bookmarks]}
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"キャッシュを保存しました: {cache_file}")


def _print_bookmarks(bookmarks: list) -> None:
    """ブックマーク一覧をコンソールに出力する（dry_run 用）"""
    import io, sys as _sys
    out = io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
    out.write("\n" + "=" * 60 + "\n")
    out.write(f"X Bookmarks ({len(bookmarks)} 件)\n")
    out.write("=" * 60 + "\n")
    for bm in bookmarks:
        like_str = f" (like:{bm.like_count:,})" if bm.like_count > 0 else ""
        out.write(f"  @{bm.author_username}{like_str}\n")
        if bm.text:
            out.write(f"    {bm.text[:100]}\n")
        out.write(f"    {bm.url}\n")
    out.write("=" * 60 + "\n")
    out.flush()
    out.detach()  # stdoutを閉じないようにする


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
        "--latest",
        action="store_true",
        default=os.environ.get("LATEST_MODE", "").lower() in ("1", "true"),
        help="処理済みIDを無視し、常に最新N件を送信する",
    )
    args = parser.parse_args()

    proc_file = PROCESSED_IDS_FILE
    if args.no_cache:
        logger.info("--no-cache: 処理済みIDキャッシュを無視します")
        proc_file = "__no_cache__"

    run_digest(
        bookmarks_file=args.bookmarks,
        processed_ids_file=proc_file,
        dry_run=args.dry_run,
        max_items=args.max_items,
        latest_mode=args.latest,
    )
