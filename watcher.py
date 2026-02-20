"""
X Bookmarks CSV 自動Push スクリプト
====================================
Chrome拡張 "X Bookmarks Exporter" がDownloadsフォルダにCSVを保存したら
自動的にgit pushしてGitHub Actionsをトリガーする。

使い方:
  python watcher.py

設定:
  WATCH_DIR    : 監視するフォルダ（デフォルト: ~/Downloads）
  REPO_DIR     : このリポジトリのパス（デフォルト: スクリプトと同じフォルダ）
  CSV_PATTERN  : 対象ファイル名のパターン（デフォルト: twitter_bookmarks*.csv）
"""

import os
import sys
import time
import shutil
import subprocess
import glob
import logging
from pathlib import Path
from datetime import datetime

# ── 設定 ──────────────────────────────────────────
WATCH_DIR = Path(os.environ.get("WATCH_DIR", Path.home() / "Downloads"))
REPO_DIR  = Path(os.environ.get("REPO_DIR",  Path(__file__).parent))
CSV_PATTERN = os.environ.get("CSV_PATTERN", "twitter_bookmarks*.csv")
DEST_FILE   = REPO_DIR / "bookmarks.json"   # .jsonという名前でCSVを保存（既存の命名に合わせる）
CHECK_INTERVAL_SEC = 10                      # 監視間隔（秒）
# ────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(REPO_DIR / "watcher.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def find_latest_csv() -> Path | None:
    """Downloadsフォルダから最新のCSVファイルを探す"""
    pattern = str(WATCH_DIR / CSV_PATTERN)
    files = glob.glob(pattern)
    if not files:
        return None
    # 更新日時が最新のファイルを返す
    return Path(max(files, key=os.path.getmtime))


def get_mtime(path: Path) -> float:
    """ファイルのmtimeを返す（存在しなければ0）"""
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def run_git(args: list[str]) -> tuple[int, str]:
    """gitコマンドを実行してreturncode, stdoutを返す"""
    result = subprocess.run(
        ["git"] + args,
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def push_to_github(csv_path: Path) -> bool:
    """
    CSVをbookmarks.jsonとしてコピーしてgit push。
    Returns True on success.
    """
    logger.info(f"新しいCSVを検出: {csv_path.name}")

    # コピー
    shutil.copy2(csv_path, DEST_FILE)
    logger.info(f"コピー完了: {csv_path.name} → {DEST_FILE.name}")

    # git操作
    steps = [
        (["add", "bookmarks.json"], "git add"),
        (["diff", "--staged", "--quiet"], "変更確認"),  # 変更なしなら終了
    ]

    code, out = run_git(["add", "bookmarks.json"])
    if code != 0:
        logger.error(f"git add 失敗: {out}")
        return False

    # 差分がなければスキップ
    code, _ = run_git(["diff", "--staged", "--quiet"])
    if code == 0:
        logger.info("bookmarks.jsonに変更なし。pushをスキップします。")
        return True

    # コミット
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    code, out = run_git(["commit", "-m", f"chore: update bookmarks ({now_str})"])
    if code != 0:
        logger.error(f"git commit 失敗: {out}")
        return False
    logger.info(f"git commit: {out.splitlines()[0] if out else 'OK'}")

    # push（remote が ahead の場合はrebase）
    code, out = run_git(["push", "origin", "main"])
    if code != 0:
        logger.warning(f"push失敗、rebaseを試みます: {out}")
        code, out = run_git(["pull", "--rebase", "origin", "main"])
        if code != 0:
            logger.error(f"git pull --rebase 失敗: {out}")
            return False
        code, out = run_git(["push", "origin", "main"])
        if code != 0:
            logger.error(f"再push失敗: {out}")
            return False

    logger.info("✅ GitHubへのpushが完了しました。GitHub Actionsがトリガーされます。")
    return True


def main():
    logger.info("=" * 50)
    logger.info(f"X Bookmarks Watcher 起動")
    logger.info(f"  監視フォルダ : {WATCH_DIR}")
    logger.info(f"  対象パターン : {CSV_PATTERN}")
    logger.info(f"  リポジトリ   : {REPO_DIR}")
    logger.info(f"  監視間隔     : {CHECK_INTERVAL_SEC}秒")
    logger.info("=" * 50)

    last_processed_mtime = 0.0

    while True:
        try:
            csv_path = find_latest_csv()

            if csv_path is not None:
                mtime = get_mtime(csv_path)
                if mtime > last_processed_mtime:
                    # 新しいファイルを検出
                    success = push_to_github(csv_path)
                    if success:
                        last_processed_mtime = mtime
                    else:
                        logger.error("push失敗。次の検出時に再試行します。")

        except KeyboardInterrupt:
            logger.info("終了します (Ctrl+C)")
            sys.exit(0)
        except Exception as e:
            logger.error(f"予期しないエラー: {e}", exc_info=True)

        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    main()
