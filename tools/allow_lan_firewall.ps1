# Run as Administrator once. Restrict access to local subnets and this application port.
$ErrorActionPreference='Stop'
$ruleName='ClinicalTutorLocalTLS'
if (-not (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name $ruleName -DisplayName 'Clinical Tutor HTTPS and RTC (local subnet)' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765,7881 -RemoteAddress LocalSubnet -Profile Any
}
if (-not (Get-NetFirewallRule -Name ($ruleName+'Media') -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name ($ruleName+'Media') -DisplayName 'Clinical Tutor encrypted RTC media (local subnet)' -Direction Inbound -Action Allow -Protocol UDP -LocalPort 7882-7982 -RemoteAddress LocalSubnet -Profile Any
}
Get-NetFirewallRule -Name $ruleName | Select-Object Name,Enabled,Profile,Action
