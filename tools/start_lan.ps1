$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$connected=@(Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.Name -notmatch 'vEthernet|WSL'} | Select-Object -ExpandProperty InterfaceIndex)
$addresses=@(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceIndex -in $connected -and $_.IPAddress -match '^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)'} | Select-Object -ExpandProperty IPAddress)
if (-not $addresses.Count) {throw 'No connected private IPv4 address. Connect Wi-Fi or Ethernet first.'}
$listener=Get-NetTCPConnection -LocalPort 8705 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $owner=Get-CimInstance Win32_Process -Filter "ProcessId=$($listener[0].OwningProcess)"
    if ($owner.CommandLine -notmatch 'backend.server:app|run_lan.py|run.py') {throw 'Port 8705 belongs to another application; stop to avoid closing it.'}
    Stop-Process -Id $owner.ProcessId
}
& (Join-Path $root '.venv/Scripts/python.exe') (Join-Path $root 'tools/start_livekit.py') --lan-address $addresses[0]
$arguments=@('tools/run_lan.py')
foreach ($address in $addresses) {$arguments+=@('--address',$address)}
Start-Process -FilePath (Join-Path $root '.venv/Scripts/python.exe') -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root 'runtime/lan.log') -RedirectStandardError (Join-Path $root 'runtime/lan.err.log')
Write-Output 'LAN HTTPS process started. Clients must trust runtime/lan-tls/clinical-tutor-ca.cer. Run tools/allow_lan_firewall.ps1 as Administrator if blocked.'
foreach ($address in $addresses) {Write-Output "https://${address}:8765/login"}
