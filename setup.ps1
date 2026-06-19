<#
  setup.ps1 - one-shot installer for band_usage on Windows.
  Pushes Claude Code & Codex subscription limits to a Samsung Galaxy Fit 3 via ntfy.

  Usage (from a normal PowerShell window):
    powershell -ExecutionPolicy Bypass -File setup.ps1 -Topic "your-private-topic"

  Optional parameters:
    -Topic            ntfy topic to publish to (your "password" - keep it private)
    -InstallDir       where to clone the repo (default: %USERPROFILE%\wearable)
    -IntervalMinutes  how often the scheduled task runs (default: 15)
    -NoSchedule       skip creating the scheduled task
#>

param(
    [string]$Topic           = "ai-limits-7f3k9q2",
    [string]$NtfyServer      = "https://ntfy.sh",
    [string]$RepoUrl         = "https://github.com/brandonkow/wearable.git",
    [string]$Branch          = "claude/samsung-fit-usage-display-xgoe5i",
    [string]$InstallDir      = (Join-Path $env:USERPROFILE "wearable"),
    [int]   $IntervalMinutes = 15,
    [switch]$NoSchedule
)

$ErrorActionPreference = "Stop"
function Info($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Warn($m) { Write-Host "    $m" -ForegroundColor Yellow }

# 1. Python -----------------------------------------------------------------
Info "Checking Python..."
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    throw "Python not found. Install it from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH'), then re-run."
}
$python = $py.Source
Ok "Python: $python"

# 2. Get the code -----------------------------------------------------------
if (Test-Path (Join-Path $InstallDir "band_usage")) {
    Info "Repo found at $InstallDir - updating..."
    Set-Location $InstallDir
    git fetch origin
    git checkout $Branch
    git pull origin $Branch
    Ok "Updated."
}
else {
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        throw "git not found and no repo at $InstallDir. Install Git from https://git-scm.com/download/win (or download the repo ZIP, extract to $InstallDir), then re-run."
    }
    Info "Cloning into $InstallDir ..."
    git clone $RepoUrl $InstallDir
    if ($LASTEXITCODE -ne 0) { throw "git clone failed." }
    Set-Location $InstallDir
    git checkout $Branch
    Ok "Cloned."
}

# 3. config.json ------------------------------------------------------------
Info "Writing config.json (topic: $Topic)..."
$config = @"
{
  "ntfy": {
    "server": "$NtfyServer",
    "topic": "$Topic",
    "token": null,
    "priority": "low"
  },
  "bar_width": 8,
  "claude": { "enabled": true, "usage_cache": "~/.claude/usage-cache.json" },
  "codex":  { "enabled": true, "sessions_dir": "~/.codex/sessions" }
}
"@
[System.IO.File]::WriteAllText((Join-Path $InstallDir "config.json"), $config)
Ok "config.json written."

# 4. Claude statusline hook -------------------------------------------------
Info "Installing Claude Code statusline hook..."
$hook = (Resolve-Path (Join-Path $InstallDir "statusline\band_statusline.py")).Path -replace '\\', '/'
$cmd  = "python $hook"
$settingsPath = Join-Path $env:USERPROFILE ".claude\settings.json"
New-Item -ItemType Directory -Force -Path (Split-Path $settingsPath) | Out-Null
if (Test-Path $settingsPath) {
    $raw = Get-Content $settingsPath -Raw
    $settings = if ([string]::IsNullOrWhiteSpace($raw)) { [pscustomobject]@{} } else { $raw | ConvertFrom-Json }
}
else {
    $settings = [pscustomobject]@{}
}
$statusLine = [pscustomobject]@{ type = "command"; command = $cmd }
$settings | Add-Member -NotePropertyName statusLine -NotePropertyValue $statusLine -Force
[System.IO.File]::WriteAllText($settingsPath, ($settings | ConvertTo-Json -Depth 10))
Ok "statusLine -> $cmd"

# 5. Preview ----------------------------------------------------------------
Info "Preview (dry run - sends nothing):"
& $python -m band_usage --config (Join-Path $InstallDir "config.json") --dry-run

# 6. Test send --------------------------------------------------------------
Info "Sending a test notification to ntfy topic '$Topic'..."
try {
    & $python -m band_usage --config (Join-Path $InstallDir "config.json")
    Ok "Sent. If your phone is subscribed to '$Topic', the card should appear."
}
catch {
    Warn "Send failed: $($_.Exception.Message)"
}

# 7. Schedule ---------------------------------------------------------------
if (-not $NoSchedule) {
    Info "Registering scheduled task 'BandUsage' (every $IntervalMinutes min, at logon, and on wake)..."
    try {
        $action = New-ScheduledTaskAction -Execute $python -Argument "-m band_usage --config config.json" -WorkingDirectory $InstallDir

        # Trigger 1: run now, then repeat every N minutes while the PC is on.
        $tRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
        # Trigger 2: at every logon (fresh card the moment you sign in).
        $tLogon = New-ScheduledTaskTrigger -AtLogOn
        $triggers = @($tRepeat, $tLogon)

        # Trigger 3 (best effort): on resume from sleep/hibernate. Windows logs
        # Power-Troubleshooter event ID 1 when the system wakes; we fire on it.
        try {
            $tWake = New-CimInstance -CimClass (Get-CimClass -ClassName MSFT_TaskEventTrigger -Namespace Root/Microsoft/Windows/TaskScheduler) -ClientOnly
            $tWake.Enabled = $true
            $tWake.Subscription = '<QueryList><Query Id="0" Path="System"><Select Path="System">*[System[Provider[@Name=''Microsoft-Windows-Power-Troubleshooter''] and (EventID=1)]]</Select></Query></QueryList>'
            $triggers += $tWake
        }
        catch {
            Warn "Wake-from-sleep trigger unavailable here; using logon + interval only."
        }

        $taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName "BandUsage" -Action $action -Trigger $triggers -Settings $taskSettings -Description "Push Claude/Codex limits to Galaxy Fit 3" -Force | Out-Null
        Ok "Scheduled: every $IntervalMinutes min, at logon, and on wake-from-sleep."
    }
    catch {
        Warn "Could not register task: $($_.Exception.Message)"
        Warn "Tip: re-run this script from an elevated (Run as administrator) PowerShell, or pass -NoSchedule to skip."
    }
}

# Summary -------------------------------------------------------------------
Write-Host ""
Info "Done! Three things still need YOU (can't be automated):"
Write-Host "  1. Phone: install the 'ntfy' app and subscribe to topic '$Topic' (server $NtfyServer)."
Write-Host "  2. Phone: Galaxy Wearable -> Notifications -> enable 'ntfy' so cards mirror to the band."
Write-Host "  3. Open Claude Code and send one message so the 5h/weekly % get cached"
Write-Host "     (the card shows 'Claude: no data' until you do this once)."
Write-Host ""
Write-Host "Re-send anytime:" -ForegroundColor Cyan
Write-Host "  cd `"$InstallDir`"; python -m band_usage --config config.json"
