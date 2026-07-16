$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Runner = Join-Path $Root "run_local_usernames.ps1"

Set-Location $Root
if (-not (Test-Path $VenvPython)) {
    python -m venv .venv
}

& $VenvPython -m pip install -r requirements.txt
& $VenvPython -m playwright install chromium

if (-not (Test-Path ".env.local")) {
    Copy-Item ".env.local.example" ".env.local"
}

$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$OnceAction = New-ScheduledTaskAction -Execute $PowerShell -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Runner`" -Mode once"
$ListenAction = New-ScheduledTaskAction -Execute $PowerShell -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Runner`" -Mode listen"
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

$DailyTriggers = @(
    New-ScheduledTaskTrigger -Daily -At "09:00"
    New-ScheduledTaskTrigger -Daily -At "21:00"
)
$LogonTrigger = New-ScheduledTaskTrigger -AtLogOn

Register-ScheduledTask -TaskName "TelegramMarketBot-Usernames-TwiceDaily" -Action $OnceAction -Trigger $DailyTriggers -Settings $Settings -Force | Out-Null
Register-ScheduledTask -TaskName "TelegramMarketBot-Username-Commands" -Action $ListenAction -Trigger $LogonTrigger -Settings $Settings -Force | Out-Null

Write-Host "Local username tasks installed. Fill .env.local, then sign out/in or start the command task manually."
