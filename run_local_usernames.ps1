param(
    [ValidateSet("once", "listen")]
    [string]$Mode = "once"
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $Root "local-logs"
$LogFile = Join-Path $LogDir ("usernames-{0}.log" -f (Get-Date -Format "yyyy-MM"))
$Python = Join-Path $Root ".venv\Scripts\python.exe"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
if (-not (Test-Path $Python)) {
    throw "Local environment is missing. Run setup_local_usernames.ps1 first."
}

Set-Location $Root
& $Python "local_usernames.py" --mode $Mode *>> $LogFile
