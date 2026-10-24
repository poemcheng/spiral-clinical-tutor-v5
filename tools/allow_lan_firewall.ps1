# Run as Administrator once. Restrict access to local subnets and this application port.
$ErrorActionPreference='Stop'
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Administrator privileges are required. Open PowerShell with Run as administrator, then run this script again.'
}
$ruleName='ClinicalTutorLocalTLS'
if (-not (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name $ruleName -DisplayName 'Clinical Tutor HTTPS and RTC (local subnet)' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765,7881 -RemoteAddress LocalSubnet -Profile Any -ErrorAction Stop | Out-Null
}
if (-not (Get-NetFirewallRule -Name ($ruleName+'Media') -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name ($ruleName+'Media') -DisplayName 'Clinical Tutor encrypted RTC media (local subnet)' -Direction Inbound -Action Allow -Protocol UDP -LocalPort 7882-7982 -RemoteAddress LocalSubnet -Profile Any -ErrorAction Stop | Out-Null
}
$result=@(foreach ($name in @($ruleName,($ruleName+'Media'))) {
    $rule=Get-NetFirewallRule -Name $name -ErrorAction Stop
    $port=$rule | Get-NetFirewallPortFilter -ErrorAction Stop
    $address=$rule | Get-NetFirewallAddressFilter -ErrorAction Stop
    if ([string]$rule.Enabled -ne 'True' -or [string]$rule.Action -ne 'Allow' -or [string]$rule.Direction -ne 'Inbound') {
        throw "Rule $name exists but is not an enabled inbound allow rule."
    }
    [pscustomobject]@{Name=$rule.Name;Enabled=[string]$rule.Enabled;Action=[string]$rule.Action;Protocol=$port.Protocol;LocalPort=($port.LocalPort -join ',');RemoteAddress=($address.RemoteAddress -join ',')}
})
$result | ConvertTo-Json -Depth 3
Write-Output 'SUCCESS: Both Clinical Tutor LAN firewall rules are installed and enabled.'
