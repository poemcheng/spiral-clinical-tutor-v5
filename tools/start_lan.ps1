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
if ($LASTEXITCODE -ne 0) {throw 'Voice server startup failed; inspect runtime/livekit.log.'}
$arguments=@('tools/run_lan.py','--background-log')
foreach ($address in $addresses) {$arguments+=@('--address',$address)}
$pythonw=Join-Path $root '.venv/Scripts/pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) {throw 'Project pythonw.exe is missing; install the Windows virtual environment first.'}
# WMI creates the host outside the launching terminal's process job.
$startup=New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow=[uint16]0}
$commandLine='"'+$pythonw+'" '+($arguments -join ' ')
$created=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$commandLine;CurrentDirectory=$root;ProcessStartupInformation=$startup}
if ($created.ReturnValue -ne 0) {throw "Independent LAN host launch failed: $($created.ReturnValue)"}
$expectedVersion=(Get-Content -LiteralPath (Join-Path $root 'package.json') -Raw | ConvertFrom-Json).version
$ready=$false
for ($attempt=0;$attempt -lt 50;$attempt++) {
    try {$health=Invoke-RestMethod -Uri 'http://127.0.0.1:8705/health' -TimeoutSec 1;if ($health.version -eq $expectedVersion) {$ready=$true;break}} catch {}
    Start-Sleep -Milliseconds 200
}
if (-not $ready) {throw 'LAN host did not become ready. Inspect runtime/lan-service.log.'}
Write-Output "LAN host verified: version $expectedVersion, PID $($created.ProcessId). Log: runtime/lan-service.log"
foreach ($address in $addresses) {Write-Output "https://${address}:8765/login"}
