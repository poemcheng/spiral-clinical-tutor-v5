$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$pythonw=Join-Path $root '.venv/Scripts/pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) {throw 'Project pythonw.exe is missing.'}
$startupFolder=[Environment]::GetFolderPath('Startup')
if (-not $startupFolder) {throw 'Current-user Startup folder is unavailable.'}
$shortcutPath=Join-Path $startupFolder 'Clinical Tutor LAN Host.lnk'
$shell=New-Object -ComObject WScript.Shell
$shortcut=$shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath=$pythonw
$shortcut.Arguments='"'+(Join-Path $root 'tools/start_lan_background.py')+'"'
$shortcut.WorkingDirectory=$root
$shortcut.WindowStyle=7
$shortcut.Description='Clinical Tutor LAN host for the current user'
$shortcut.Save()
Write-Output "Current-user sign-in startup installed: $shortcutPath"
