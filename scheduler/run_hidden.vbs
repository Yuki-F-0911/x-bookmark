Set WinScriptHost = CreateObject("WScript.Shell")
WinScriptHost.Run Chr(34) & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\start_watcher.bat" & Chr(34), 0
Set WinScriptHost = Nothing
