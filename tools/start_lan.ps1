$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$connected=@(Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.Name -notmatch 'vEthernet|WSL'} | Select-Object -ExpandProperty InterfaceIndex)
$addresses=@(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceIndex -in $connected -and $_.IPAddress -match '^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)'} | Select-Object -ExpandProperty IPAddress)
if (-not $addresses.Count) {throw '找不到同網路 IPv4 位址，請先連線 Wi-Fi 或乙太網路。'}
$listener=Get-NetTCPConnection -LocalPort 8705 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $owner=Get-CimInstance Win32_Process -Filter "ProcessId=$($listener[0].OwningProcess)"
    if ($owner.CommandLine -notmatch 'backend.server:app|run_lan.py|run.py') {throw '8705 由其他程式使用，停止以避免誤關閉。'}
    Stop-Process -Id $owner.ProcessId
}
& (Join-Path $root '.venv/Scripts/python.exe') (Join-Path $root 'tools/start_livekit.py') --lan-address $addresses[0]
$arguments=@('tools/run_lan.py')
foreach ($address in $addresses) {$arguments+=@('--address',$address)}
Start-Process -FilePath (Join-Path $root '.venv/Scripts/python.exe') -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root 'runtime/lan.log') -RedirectStandardError (Join-Path $root 'runtime/lan.err.log')
Write-Output '同網路 HTTPS 服務已啟動。首次用手機需安裝 runtime/lan-tls/clinical-tutor-ca.cer；若無法連線，請用系統管理員執行 tools/allow_lan_firewall.ps1。'
foreach ($address in $addresses) {Write-Output "https://${address}:8765/login"}
