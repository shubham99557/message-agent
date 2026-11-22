Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
strBatPath = strScriptDir & "\start_acttrident_desktop.bat"
strRepoRoot = fso.GetParentFolderName(strScriptDir)
WshShell.CurrentDirectory = strRepoRoot
WshShell.Run chr(34) & strBatPath & chr(34), 0, False
Set WshShell = Nothing
Set fso = Nothing
