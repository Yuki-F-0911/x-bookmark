@echo off
REM X Bookmarks Watcher 起動スクリプト
REM タスクスケジューラから呼び出すか、ダブルクリックで起動してください

cd /d "%~dp0"

REM Python環境の確認
python --version >nul 2>&1
if errorlevel 1 (
    echo Python が見つかりません。Pythonをインストールしてください。
    pause
    exit /b 1
)

REM 依存パッケージの確認（初回のみインストール）
pip show watchdog >nul 2>&1

echo ========================================
echo  X Bookmarks Watcher を起動します
echo  Ctrl+C で停止
echo ========================================
echo.

python watcher.py

REM エラー終了時に一時停止
if errorlevel 1 (
    echo.
    echo エラーが発生しました。ログを確認してください: watcher.log
    pause
)
