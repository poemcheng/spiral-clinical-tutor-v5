$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot 'runtime/internet-tools/cloudflared.exe'))) {
    & (Join-Path $taskRoot '.venv/Scripts/python.exe') (Join-Path $taskRoot 'tools/install_cloudflared.py')
    if ($LASTEXITCODE -ne 0) {throw 'Official connector installation failed.'}
}
$taskState=Join-Path $taskRoot 'runtime/internet-service.json'
if (Test-Path -LiteralPath $taskState) {
    $taskProcessId=(Get-Content -Raw -LiteralPath $taskState | ConvertFrom-Json).pid
    $taskExisting=Get-CimInstance Win32_Process -Filter "ProcessId=$taskProcessId" -ErrorAction SilentlyContinue
    if ($taskExisting -and $taskExisting.CommandLine -match 'tools[/\\]internet_service.py') {Write-Output 'Internet and backup supervisor already running.';exit 0}
}
$taskPython=Join-Path $taskRoot '.venv/Scripts/pythonw.exe'
$taskStartup=New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow=[uint16]0}
$taskCreated=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=('"'+$taskPython+'" tools/internet_service.py');CurrentDirectory=$taskRoot;ProcessStartupInformation=$taskStartup}
if ($taskCreated.ReturnValue -ne 0) {throw 'Internet supervisor launch failed.'}
Write-Output "Internet and encrypted backup supervisor started: $($taskCreated.ProcessId)"
