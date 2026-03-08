# Windows Task Scheduler Registration Script
# Run PowerShell as Administrator:
#   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
#   .\setup_task_scheduler.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

# ============================================================
# Task 1: CSV Watcher（ログオン時に常駐）
# ============================================================
$WatcherTask = "XBookmarkWatcher"

if (Get-ScheduledTask -TaskName $WatcherTask -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $WatcherTask -Confirm:$false
    Write-Host "Removed existing task: $WatcherTask"
}

$VbsFile = Join-Path $ScriptDir "run_hidden.vbs"
$WatcherAction = New-ScheduledTaskAction -Execute "wscript.exe" -Argument ("`"" + $VbsFile + "`"") -WorkingDirectory $ProjectDir
$WatcherTrigger = New-ScheduledTaskTrigger -AtLogOn
$WatcherSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 24) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $WatcherTask -Action $WatcherAction -Trigger $WatcherTrigger -Settings $WatcherSettings -Principal $Principal -Description "X Bookmarks CSV Watcher - auto push to GitHub"

Write-Host "Registered: $WatcherTask (at logon)"

# ============================================================
# Task 2: Daily Pipeline（毎日 AM 9:00）
# ============================================================
$DailyTask = "XBookmarkDailyPipeline"

if (Get-ScheduledTask -TaskName $DailyTask -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $DailyTask -Confirm:$false
    Write-Host "Removed existing task: $DailyTask"
}

$DailyBat = Join-Path $ScriptDir "daily_run.bat"
$DailyAction = New-ScheduledTaskAction -Execute $DailyBat -WorkingDirectory $ProjectDir
$DailyTrigger = New-ScheduledTaskTrigger -Daily -At "09:00"
$DailySettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -StartWhenAvailable -WakeToRun

Register-ScheduledTask -TaskName $DailyTask -Action $DailyAction -Trigger $DailyTrigger -Settings $DailySettings -Principal $Principal -Description "Daily digest + newsletter + Naruse themes pipeline"

Write-Host "Registered: $DailyTask (daily at 09:00)"

# ============================================================
Write-Host ""
Write-Host "========================================"
Write-Host " All tasks registered successfully!"
Write-Host "========================================"
Write-Host ""
Write-Host "Tasks:"
Write-Host "  1. $WatcherTask     - CSV watcher (at logon)"
Write-Host "  2. $DailyTask       - Full pipeline (daily 09:00)"
Write-Host ""
Write-Host "To start now:"
Write-Host "  Start-ScheduledTask -TaskName $WatcherTask"
Write-Host "  Start-ScheduledTask -TaskName $DailyTask"
Write-Host ""
Write-Host "To check status:"
Write-Host "  Get-ScheduledTask -TaskName 'XBookmark*' | Format-Table TaskName, State"
