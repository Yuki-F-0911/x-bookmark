#!/usr/bin/env python3
"""
統合型パイプライン：手動ブックマーク＋自動取得記事を処理

毎日実行フロー：
1. 手動ブックマークを処理
2. 複数ソースから新規記事を自動取得
3. 両方をマージして分類・スコアリング
4. 成瀬さんのnote題材リストを生成

使い方:
  python integrated_daily_pipeline.py                    # フル実行
  python integrated_daily_pipeline.py --skip-auto        # 手動ブックマークのみ
  python integrated_daily_pipeline.py --skip-manual      # 自動取得のみ
  python integrated_daily_pipeline.py --setup            # 定期実行セットアップ
"""

import json
import sys
import io
from datetime import datetime
from pathlib import Path
from subprocess import run, PIPE
import shutil

# Windows環境でのUTF-8出力対応
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
NARUSE_THEMES_DIR = PROJECT_ROOT.parent / "WillForward" / "PersonalizeData" / "naruse" / "note_themes"
MERGED_DATA_FILE = PROJECT_ROOT / "data" / "merged_sources_today.json"


def log_message(message, level="INFO"):
    """ログ出力"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def run_script(script_path, args=None):
    """スクリプトを実行してJSONを取得"""
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    try:
        result = run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def extract_json_from_output(stdout, stderr):
    """実行結果からJSONを抽出"""
    try:
        # JSON形式の出力を探す
        if "{" in stdout:
            start = stdout.rfind("{")
            end = stdout.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(stdout[start:end])
    except json.JSONDecodeError:
        pass
    return None


def step1_process_manual_bookmarks():
    """ステップ1: 手動ブックマークを処理"""
    log_message("ステップ1: 手動ブックマークを処理")

    if not (PROJECT_ROOT / "data" / "bookmarks.json").exists():
        log_message("  ℹ bookmarks.json が見つかりません", "INFO")
        return []

    # bookmarks.json を中間ファイルにコピー
    temp_file = PROJECT_ROOT / "temp_manual_bookmarks.json"
    shutil.copy(PROJECT_ROOT / "data" / "bookmarks.json", temp_file)

    log_message("  ✓ bookmarks.json を読み込み完了")
    return temp_file


def step2_fetch_auto_articles():
    """ステップ2: 複数ソースから記事を自動取得"""
    log_message("\nステップ2: 複数ソースから記事を自動取得")

    script_path = SCRIPT_DIR.parent / "auto_fetch_business_articles.py"

    if not script_path.exists():
        log_message("  ⚠ auto_fetch_business_articles.py が見つかりません", "WARN")
        return None

    success, stdout, stderr = run_script(script_path, ["--source", "all"])

    if success:
        # 出力からJSONパスを抽出
        import re
        output = (stdout or "") + (stderr or "")
        match = re.search(r"auto_fetched_articles[^'\"]*\.json", output)
        if match:
            articles_file = PROJECT_ROOT / match.group()
            if articles_file.exists():
                log_message(f"  ✓ 自動取得完了: {articles_file.name}")
                return articles_file

    log_message("  ⚠ 自動取得スキップ（準備中）", "WARN")
    return None


def step3_merge_sources(manual_file, auto_file):
    """ステップ3: 複数ソースをマージ"""
    log_message("\nステップ3: 複数ソースをマージ")

    merged_items = []

    # 手動ブックマーク
    if manual_file and manual_file.exists():
        try:
            with open(manual_file, "r", encoding="utf-8") as f:
                manual_data = json.load(f)
            if isinstance(manual_data, list):
                merged_items.extend(manual_data)
            log_message(f"  ✓ 手動ブックマーク: {len(manual_data)}件")
        except Exception as e:
            log_message(f"  ✗ 手動ブックマーク読み込み失敗: {e}", "ERROR")

    # 自動取得記事
    if auto_file and auto_file.exists():
        try:
            with open(auto_file, "r", encoding="utf-8") as f:
                auto_data = json.load(f)
            articles = auto_data.get("articles", [])
            merged_items.extend(articles)
            log_message(f"  ✓ 自動取得記事: {len(articles)}件")
        except Exception as e:
            log_message(f"  ✗ 自動取得記事読み込み失敗: {e}", "ERROR")

    log_message(f"  📊 マージ後: {len(merged_items)}件")

    # マージ結果を保存
    with open(MERGED_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(merged_items, f, ensure_ascii=False, indent=2)

    return merged_items


def step4_classify_and_score(merged_items):
    """ステップ4: テーマ分類・スコアリング"""
    log_message("\nステップ4: テーマ分類・スコアリング")

    if not merged_items:
        log_message("  ⚠ マージ対象がありません", "WARN")
        return None

    # merge済みJSONをbookmarks.json形式に変換して処理
    # (extract_business_themes.pyが期待する形式)

    script_path = SCRIPT_DIR / "extract_business_themes.py"

    if not script_path.exists():
        log_message("  ⚠ extract_business_themes.py が見つかりません", "WARN")
        return None

    success, stdout, stderr = run_script(
        script_path,
        ["--limit", str(len(merged_items)), "--output", f"themes_{datetime.now().strftime('%Y%m%d_integrated')}.md"]
    )

    if success:
        log_message("  ✓ テーマ分類・スコアリング完了")
        return True
    else:
        log_message(f"  ✗ テーマ分類失敗: {stderr[:200]}", "ERROR")
        return False


def pipeline(skip_manual=False, skip_auto=False):
    """メインパイプライン"""
    log_message("=" * 70)
    log_message("統合パイプライン：手動ブックマーク＋自動取得記事を処理", "START")
    log_message("=" * 70)

    manual_file = None
    auto_file = None

    # ステップ1: 手動ブックマーク
    if not skip_manual:
        manual_file = step1_process_manual_bookmarks()

    # ステップ2: 自動取得
    if not skip_auto:
        auto_file = step2_fetch_auto_articles()

    # ステップ3: マージ
    merged_items = step3_merge_sources(manual_file, auto_file)

    # ステップ4: 分類・スコアリング
    if merged_items:
        step4_classify_and_score(merged_items)

    # クリーンアップ
    if manual_file and manual_file.exists():
        manual_file.unlink()

    # 完了
    log_message("\n" + "=" * 70)
    log_message("パイプライン完了", "DONE")
    log_message("=" * 70)

    # ログ記録
    log_file = SCRIPT_DIR / "integrated_pipeline_logs.txt"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now().isoformat()}] パイプライン実行完了\n")


def setup_scheduler_command():
    """タスクスケジューラー用のセットアップコマンドを出力"""
    script_path = Path(__file__).resolve()
    work_dir = script_path.parent

    print("\n" + "=" * 70)
    print("📅 統合パイプライン - タスクスケジューラー設定方法（Windows）")
    print("=" * 70)
    print(f"""
【PowerShell（管理者権限）で実行】

1. 以下のコマンドをコピー・ペースト:

$trigger = New-ScheduledTaskTrigger -Daily -At 09:30
$action = New-ScheduledTaskAction -Execute 'python.exe' `
  -Argument '{script_path}' `
  -WorkingDirectory '{work_dir}'
$settings = New-ScheduledTaskSettingsSet -RunOnlyIfNetworkAvailable
Register-ScheduledTask -TaskName "NaruseNoteThemesIntegratedDaily" `
  -Trigger $trigger -Action $action -Settings $settings

2. 確認コマンド:
Get-ScheduledTask -TaskName "NaruseNoteThemesIntegratedDaily"

3. 実行テスト:
Start-ScheduledTask -TaskName "NaruseNoteThemesIntegratedDaily"

4. ログ確認:
Get-Content {work_dir}\\integrated_pipeline_logs.txt -Tail 30

【実行スケジュール】
- 毎日午前9時30分（デフォルト：手動ブックマーク処理）
- 毎日午前9時：daily_business_themes_pipeline.py（既存）
- 毎日午前9時30分：integrated_daily_pipeline.py（新規：統合版）

※ 自動取得記事の取得タイミングをずらすことで、重複を避けつつ
  手動ブックマークと自動取得の両方を最大限活用できます。
""")
    print("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="統合パイプライン：手動ブックマーク＋自動取得記事を処理"
    )
    parser.add_argument("--skip-manual", action="store_true", help="手動ブックマークをスキップ")
    parser.add_argument("--skip-auto", action="store_true", help="自動取得をスキップ")
    parser.add_argument("--setup", action="store_true", help="タスクスケジューラー設定")
    args = parser.parse_args()

    if args.setup:
        setup_scheduler_command()
    else:
        NARUSE_THEMES_DIR.mkdir(parents=True, exist_ok=True)
        pipeline(skip_manual=args.skip_manual, skip_auto=args.skip_auto)
