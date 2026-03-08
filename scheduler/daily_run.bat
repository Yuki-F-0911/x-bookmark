@echo off
REM ============================================================
REM  日次フルパイプライン実行スクリプト
REM  タスクスケジューラーから毎日 AM 9:00 に起動
REM
REM  処理内容:
REM    1. ブックマーク要約 → Slack通知
REM    2. ニュースレター記事生成（Note形式）
REM    3. 成瀬さんnote題材の自動取得・分類
REM ============================================================

cd /d "%~dp0\.."

REM Python確認
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python が見つかりません
    exit /b 1
)

REM ログファイル
set LOGFILE=data\daily_pipeline_%date:~0,4%%date:~5,2%%date:~8,2%.log

echo ===== Daily Pipeline Start: %date% %time% ===== >> %LOGFILE%

REM --- Step 1: ブックマークダイジェスト（Slack通知） ---
echo [Step 1] ブックマークダイジェスト >> %LOGFILE%
python -m src.main --skip-enrich >> %LOGFILE% 2>&1

REM --- Step 2: ニュースレター記事生成 ---
echo [Step 2] ニュースレター記事生成 >> %LOGFILE%
python scripts\generate_newsletter.py --format note --output %date:~0,4%-%date:~5,2%-%date:~8,2%.md >> %LOGFILE% 2>&1

REM --- Step 3: 成瀬さんnote題材取得 ---
echo [Step 3] 成瀬テーマ抽出 >> %LOGFILE%
python scripts\naruse\integrated_daily_pipeline.py >> %LOGFILE% 2>&1

echo ===== Daily Pipeline End: %date% %time% ===== >> %LOGFILE%
