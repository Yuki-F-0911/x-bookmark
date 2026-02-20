# Windowsタスクスケジューラ登録スクリプト
# PowerShellを管理者権限で実行してください:
#   右クリック → "管理者として実行" → このスクリプトを実行
#
# または PowerShell で:
#   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
#   .\setup_task_scheduler.ps1

$TaskName    = "XBookmarkWatcher"
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatFile     = Join-Path $ScriptDir "start_watcher.bat"
$PythonPath  = (Get-Command python).Source

# 既存タスクがあれば削除
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "既存タスクを削除しました: $TaskName"
}

# タスクの設定
$Action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatFile`"" -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn   # ログイン時に自動起動
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 24) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

# タスク登録
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "X Bookmarks CSVを監視してGitHubへ自動Push"

Write-Host ""
Write-Host "✅ タスクスケジューラに登録しました: $TaskName"
Write-Host "   次回ログイン時から自動で起動します"
Write-Host ""
Write-Host "今すぐ起動する場合:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
