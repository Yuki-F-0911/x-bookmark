# Windows Task Scheduler Registration Script
# Run PowerShell as Administrator:
#   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
#   .\setup_task_scheduler.ps1

$TaskName    = "XBookmarkWatcher"
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatFile     = Join-Path $ScriptDir "start_watcher.bat"

# Remove existing task
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task: $TaskName"
}

# Task configuration
$Action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument ("/c " + $BatFile) -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 24) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

# Register task
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "X Bookmarks CSV Watcher - auto push to GitHub"

Write-Host ""
Write-Host "Task registered: $TaskName"
Write-Host "It will start automatically at next logon."
Write-Host ""
Write-Host "To start now:"
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
