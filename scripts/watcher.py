"""
X Bookmarks CSV 自動Push スクリプト
====================================
Chrome拡張 "X Bookmarks Exporter" がDownloadsフォルダにCSVを保存したら
自動的にgit pushしてGitHub Actionsをトリガーする。

重複防止:
  - CSVの内容ハッシュを記録し、内容が同じなら再pushしない
  - 起動時にリモートからpullして processed_ids.json を同期
  - git diff --staged で変更がなければスキップ

使い方:
  python watcher.py

設定:
  WATCH_DIR    : 監視するフォルダ（デフォルト: ~/Downloads）
  REPO_DIR     : このリポジトリのパス（デフォルト: スクリプトと同じフォルダ）
  CSV_PATTERN  : 対象ファイル名のパターン（デフォルト: bookmarks*.csv）
"""

import os
import sys
import time
import hashlib
import shutil
import subprocess
import glob
import logging
from pathlib import Path
from datetime import datetime

# ── 設定 ──────────────────────────────────────────
WATCH_DIR = Path(os.environ.get("WATCH_DIR", Path.home() / "Downloads"))
REPO_DIR  = Path(os.environ.get("REPO_DIR",  Path(__file__).parent.parent))
CSV_PATTERN = os.environ.get("CSV_PATTERN", "bookmarks*.csv")
DEST_FILE   = REPO_DIR / "data" / "bookmarks.json"
HASH_FILE   = REPO_DIR / ".last_csv_hash"
CHECK_INTERVAL_SEC = 10
# ────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(REPO_DIR / "data" / "watcher.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def find_all_csvs() -> list[Path]:
    """Downloadsフォルダから全てのbookmarks CSVファイルを返す（更新日時降順）"""
    pattern = str(WATCH_DIR / CSV_PATTERN)
    files = glob.glob(pattern)
    return sorted([Path(f) for f in files], key=os.path.getmtime, reverse=True)


def find_latest_csv() -> Path | None:
    """Downloadsフォルダから最新のCSVファイルを探す"""
    csvs = find_all_csvs()
    return csvs[0] if csvs else None


def file_hash(path: Path) -> str:
    """ファイルの内容ハッシュ（SHA256）を返す"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def combined_hash(paths: list[Path]) -> str:
    """複数ファイルの合算ハッシュを返す（ファイル名ソート順で安定化）"""
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda x: x.name):
        h.update(p.name.encode("utf-8"))
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    return h.hexdigest()


def load_last_hash() -> str:
    """前回処理したCSVのハッシュを読み込む"""
    try:
        return HASH_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def save_last_hash(h: str) -> None:
    """CSVのハッシュを保存"""
    HASH_FILE.write_text(h, encoding="utf-8")


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


def sync_remote() -> None:
    """リモートの変更（processed_ids.json等）をpullして同期"""
    code, out = run_git(["pull", "--rebase", "origin", "main"])
    if code == 0:
        logger.info("リモートと同期しました")
    else:
        logger.warning(f"リモート同期に失敗（後続で再試行）: {out}")


def push_to_github(csv_paths: list[Path]) -> bool:
    """
    全CSVをマージして読み込み、ローカル環境でテキスト補完を行ってから
    bookmarks.jsonとして保存してgit push。
    Returns True on success.
    """
    logger.info(f"CSVファイル {len(csv_paths)} 件をマージ処理します")
    for p in csv_paths:
        logger.info(f"  - {p.name}")

    # リモートから最新を取得（processed_ids.json等の競合防止）
    sync_remote()

    import json
    # パスを通す（srcモジュールをインポートするため）
    if str(REPO_DIR) not in sys.path:
        sys.path.insert(0, str(REPO_DIR))

    from src.bookmark_loader import load_bookmarks

    try:
        logger.info("全CSVをパースし、マージ・重複除去・テキスト補完を行います...")

        # 全CSVを読み込んでマージ（IDで重複除去、テキストがある方を優先）
        merged: dict[str, dict] = {}
        for csv_path in csv_paths:
            try:
                bookmarks = load_bookmarks(str(csv_path))
                for bm in bookmarks:
                    if bm.id not in merged:
                        merged[bm.id] = {
                            "id": bm.id,
                            "text": bm.text,
                            "author_name": bm.author_name,
                            "author_username": bm.author_username,
                            "url": bm.url,
                            "created_at": bm.created_at.isoformat() if bm.created_at else None,
                            "like_count": bm.like_count,
                            "retweet_count": bm.retweet_count,
                            "reply_count": bm.reply_count,
                        }
                    elif bm.text and not merged[bm.id].get("text"):
                        # 既存エントリにテキストがなければ上書き
                        merged[bm.id]["text"] = bm.text
            except Exception as e:
                logger.warning(f"CSV読み込みエラー ({csv_path.name}): {e}")
                continue

        # created_at降順でソート
        bookmark_dicts = sorted(
            merged.values(),
            key=lambda x: x.get("created_at") or "",
            reverse=True,
        )

        # JSONとして書き出す
        with open(DEST_FILE, "w", encoding="utf-8") as f:
            json.dump(bookmark_dicts, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON変換・保存完了: {DEST_FILE.name} ({len(bookmark_dicts)}件, {len(csv_paths)}ファイルからマージ)")
    except Exception as e:
        logger.error(f"ブックマーク変換エラー: {e}", exc_info=True)
        return False

    # git add
    code, out = run_git(["add", "data/bookmarks.json"])
    if code != 0:
        logger.error(f"git add 失敗: {out}")
        return False

    # 差分がなければスキップ（内容が完全に同じ場合）
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

    # push
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

    logger.info("GitHubへのpushが完了しました。GitHub Actionsがトリガーされます。")
    return True


def main():
    logger.info("=" * 50)
    logger.info("X Bookmarks Watcher 起動")
    logger.info(f"  監視フォルダ : {WATCH_DIR}")
    logger.info(f"  対象パターン : {CSV_PATTERN}")
    logger.info(f"  リポジトリ   : {REPO_DIR}")
    logger.info(f"  監視間隔     : {CHECK_INTERVAL_SEC}秒")
    logger.info("=" * 50)

    # 起動時にリモートと同期
    sync_remote()

    last_hash = load_last_hash()
    if last_hash:
        logger.info(f"前回のCSVハッシュ: {last_hash[:16]}...")

    while True:
        try:
            csv_paths = find_all_csvs()

            if csv_paths:
                current_hash = combined_hash(csv_paths)

                if current_hash != last_hash:
                    # いずれかのCSVが変わった（追加・更新）
                    logger.info(f"CSVの変更を検出（{len(csv_paths)}ファイル）")
                    success = push_to_github(csv_paths)
                    if success:
                        save_last_hash(current_hash)
                        last_hash = current_hash
                    else:
                        logger.error("push失敗。次回再試行します。")

        except KeyboardInterrupt:
            logger.info("終了します (Ctrl+C)")
            sys.exit(0)
        except Exception as e:
            logger.error(f"予期しないエラー: {e}", exc_info=True)

        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    main()
