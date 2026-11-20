Set WshShell = CreateObject("WScript.Shell")
strCurDir = WshShell.CurrentDirectory
WshShell.Run chr(34) & strCurDir & "\scripts\start_acttrident_desktop.bat" & chr(34), 0, False
Set WshShell = Nothing
