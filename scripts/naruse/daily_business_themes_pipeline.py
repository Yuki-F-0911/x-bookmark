#!/usr/bin/env python3
"""
成瀬さんのnote題材を毎日自動取得・分類するパイプライン

このスクリプトをタスクスケジューラーで毎日実行すると：
1. ビジネス話題を自動取得
2. 成瀬さんのパーソナリティに基づいて分類・スコアリング
3. 高親和度テーマを note_themes/ に保存

使い方:
  python daily_business_themes_pipeline.py

タスクスケジューラー設定例（Windows）:
  - トリガー: 毎日午前9時
  - アクション: python.exe C:\\Users\\yuki0\\x-bookmark-digest\\daily_business_themes_pipeline.py
  - 作業フォルダ: C:\\Users\\yuki0\\x-bookmark-digest
"""

import json
import sys
import io
from datetime import datetime
from pathlib import Path
from subprocess import run, PIPE

# Windows環境でのUTF-8出力対応
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
NARUSE_THEMES_DIR = PROJECT_ROOT.parent / "WillForward" / "PersonalizeData" / "naruse" / "note_themes"


def log_message(message, level="INFO"):
    """ログ出力"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def run_script(script_path, args=None):
    """スクリプトを実行"""
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    try:
        result = run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def pipeline():
    """メインパイプライン"""
    log_message("=" * 60)
    log_message("成瀬さんのnote題材 日次取得パイプイン開始", "START")
    log_message("=" * 60)

    # ステップ1: ブックマークから既存テーマを取得（存在する場合）
    if (PROJECT_ROOT / "data" / "bookmarks.json").exists():
        log_message("ステップ1: data/bookmarks.json から既存ブックマークを処理")

        output_file = NARUSE_THEMES_DIR / f"themes_{datetime.now().strftime('%Y%m%d')}.md"
        success, stdout, stderr = run_script(
            SCRIPT_DIR / "extract_business_themes.py",
            ["--limit", "50", "--output", output_file.name]
        )

        if success:
            log_message(f"  ✓ テーマ抽出完了: {output_file}")
        else:
            log_message(f"  ✗ テーマ抽出失敗: {stderr}", "ERROR")

    # ステップ2: Web検索で新規話題を取得（統合スクリプト経由）
    log_message("\nステップ2: Web検索で新規ビジネス話題を取得")

    websearch_script = SCRIPT_DIR.parent / "fetch_with_websearch.py"
    if websearch_script.exists():
        success, stdout, stderr = run_script(websearch_script)

        if success:
            log_message("  ✓ Web検索完了")
        else:
            log_message("  ⚠ Web検索スキップ（スクリプト準備中）", "WARN")
    else:
        log_message("  ⚠ Web検索スクリプトが見つかりません", "WARN")

    # ステップ3: サマリー統計を生成
    log_message("\nステップ3: 統計情報を生成")

    themes_files = list(NARUSE_THEMES_DIR.glob("*.md"))
    if themes_files:
        latest_file = max(themes_files, key=lambda p: p.stat().st_mtime)
        log_message(f"  ✓ 最新テーマリスト: {latest_file.name}")
        log_message(f"  ✓ 保存先: {NARUSE_THEMES_DIR}")
    else:
        log_message("  ℹ テーマファイルが見つかりません", "INFO")

    # 実行結果を記録
    log_message("\n" + "=" * 60)
    log_message("パイプライン完了", "DONE")
    log_message("=" * 60)

    # ログファイルに記録
    log_file = SCRIPT_DIR / "pipeline_logs.txt"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now().isoformat()}] パイプライン実行完了\n")


def setup_scheduler_command():
    """タスクスケジューラー用のセットアップコマンドを出力"""
    script_path = Path(__file__).resolve()
    work_dir = script_path.parent

    print("\n" + "=" * 70)
    print("📅 タスクスケジューラー設定方法（Windows）")
    print("=" * 70)
    print(f"""
【PowerShell（管理者権限）で実行】

1. 以下のコマンドをコピー・ペースト:

$trigger = New-ScheduledTaskTrigger -Daily -At 09:00
$action = New-ScheduledTaskAction -Execute 'python.exe' `
  -Argument '{script_path}' `
  -WorkingDirectory '{work_dir}'
$settings = New-ScheduledTaskSettingsSet -RunOnlyIfNetworkAvailable
Register-ScheduledTask -TaskName "NaruseNoteThemesDaily" `
  -Trigger $trigger -Action $action -Settings $settings

【陸上競技知識サービス向け（オプション）】
$athletics_script = '{work_dir}\\fetch_athletics_topics_v2.py'
$action_ath = New-ScheduledTaskAction -Execute 'python.exe' `
  -Argument $athletics_script `
  -WorkingDirectory '{work_dir}'
Register-ScheduledTask -TaskName "AthleticsKnowledgeDaily" `
  -Trigger $trigger -Action $action_ath -Settings $settings

2. 確認コマンド:
Get-ScheduledTask -TaskName "NaruseNoteThemesDaily"
Get-ScheduledTask -TaskName "AthleticsKnowledgeDaily"

3. 実行テスト:
Start-ScheduledTask -TaskName "NaruseNoteThemesDaily"
Start-ScheduledTask -TaskName "AthleticsKnowledgeDaily"

4. ログ確認:
Get-Content {work_dir}\\pipeline_logs.txt -Tail 20
""")
    print("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="成瀬さんのnote題材を毎日自動取得するパイプライン"
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="タスクスケジューラー設定コマンドを表示"
    )
    args = parser.parse_args()

    if args.setup:
        setup_scheduler_command()
    else:
        NARUSE_THEMES_DIR.mkdir(parents=True, exist_ok=True)
        pipeline()
