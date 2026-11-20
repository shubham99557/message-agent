# ActTrident Windows Desktop & Start Menu Shortcut Generator
$WshShell = New-Object -ComObject WScript.Shell
$repoRoot = (Get-Item $PSScriptRoot\..).FullName

$launcherTarget = Join-Path $repoRoot "scripts\start_acttrident_desktop.bat"
$vbsTarget = Join-Path $repoRoot "scripts\ActTrident.vbs"

# 1. Desktop Shortcut
$desktopPath = [Environment]::GetFolderPath('Desktop')
$desktopLnk = Join-Path $desktopPath "ActTrident AI Sales Agent.lnk"

$shortcut = $WshShell.CreateShortcut($desktopLnk)
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = "`"$vbsTarget`""
$shortcut.WorkingDirectory = $repoRoot
$shortcut.Description = "ActTrident Local AI Sales Outreach & Research Agent"
$shortcut.Save()
Write-Host "Created Desktop Shortcut: $desktopLnk"

# 2. Start Menu Shortcut
$startMenuPath = Join-Path ([Environment]::GetFolderPath('Programs')) "ActTrident"
if (-not (Test-Path $startMenuPath)) {
    New-Item -ItemType Directory -Path $startMenuPath -Force | Out-Null
}
$startMenuLnk = Join-Path $startMenuPath "ActTrident AI Sales Agent.lnk"

$smShortcut = $WshShell.CreateShortcut($startMenuLnk)
$smShortcut.TargetPath = "wscript.exe"
$smShortcut.Arguments = "`"$vbsTarget`""
$smShortcut.WorkingDirectory = $repoRoot
$smShortcut.Description = "ActTrident Local AI Sales Outreach & Research Agent"
$smShortcut.Save()
Write-Host "Created Start Menu Shortcut: $startMenuLnk"
