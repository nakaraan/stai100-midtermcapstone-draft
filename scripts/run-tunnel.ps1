# Exposes the already-running API (:8000) and UI (:8501) publicly via two
# Cloudflare *quick* tunnels - no Cloudflare account needed, but the URLs are
# anonymous, unauthenticated, and change every time this is run.
#
#   powershell -File scripts\run-all.ps1 -Tunnel     # normal path: run-all calls this
#   powershell -File scripts\run-tunnel.ps1           # or standalone, once run-all is up
#
# Known Cloudflare free-tier limit: ~100s hard timeout on the proxied request
# (524 error past that, can't be raised without an Enterprise account) - fine for
# qwen2.5:7b's observed ~26-57s /chat latency, worth knowing if a query runs long.
. "$PSScriptRoot\common.ps1"
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root "scripts\logs"

Write-Step "cloudflared"
$cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
$cf = if ($cmd) { $cmd.Source } else { $null }
if (-not $cf) {
    $fallback = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    if (Test-Path $fallback) {
        $cf = $fallback
    } else {
        Write-Warn "not found - installing via winget"
        winget install --id Cloudflare.cloudflared -e --accept-package-agreements --accept-source-agreements
        # winget updates the registry, not this already-running process's PATH -
        # without this refresh, `cloudflared` stays "not found" until a new shell.
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
        $cf = if ($cmd) { $cmd.Source } elseif (Test-Path $fallback) { $fallback } else { $null }
    }
}
if (-not $cf -or -not (Test-Path $cf)) {
    Write-Err "cloudflared install failed - install manually: https://github.com/cloudflare/cloudflared/releases"
    exit 1
}
Write-Ok "using $cf"

if (-not (Test-PortListening 8000)) { Write-Err "API isn't running on :8000 - run scripts\run-all.ps1 first"; exit 1 }
if (-not (Test-PortListening 8501)) { Write-Err "UI isn't running on :8501 - run scripts\run-all.ps1 first"; exit 1 }

$existing = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($existing) {
    Write-Warn "cloudflared is already running (PID $($existing.Id -join ', ')) - not starting duplicate tunnels."
    Write-Warn "Run scripts\stop-all.ps1 first if you want fresh URLs, then re-run this script."
    Write-Step "Last known URLs (from scripts\logs\cf-*.err.log)"
    # Test-Path first: Select-String -Path on a missing file throws at parameter
    # binding, before its own -ErrorAction SilentlyContinue can suppress it (seen
    # firsthand - these logs won't exist yet if the running tunnels were started
    # by hand rather than by this script).
    if (Test-Path "$logDir\cf-api.err.log") {
        Select-String -Path "$logDir\cf-api.err.log" -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -Last 1
    }
    if (Test-Path "$logDir\cf-ui.err.log") {
        Select-String -Path "$logDir\cf-ui.err.log" -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -Last 1
    }
    if (-not (Test-Path "$logDir\cf-api.err.log") -and -not (Test-Path "$logDir\cf-ui.err.log")) {
        Write-Warn "no log from this script yet - these tunnels were started outside it, so the URLs aren't on disk here."
    }
    exit 0
}

Write-Step "starting tunnels"
Start-Logged -FilePath $cf -WorkingDirectory $root -LogDir $logDir -Name "cf-api" -ArgumentList @("tunnel", "--url", "http://localhost:8000") | Out-Null
Start-Logged -FilePath $cf -WorkingDirectory $root -LogDir $logDir -Name "cf-ui"  -ArgumentList @("tunnel", "--url", "http://localhost:8501") | Out-Null

$apiUrl = $null; $uiUrl = $null
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 2
    if (-not $apiUrl -and (Test-Path "$logDir\cf-api.err.log")) {
        $m = Select-String -Path "$logDir\cf-api.err.log" -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
        if ($m) { $apiUrl = $m.Matches[0].Value }
    }
    if (-not $uiUrl -and (Test-Path "$logDir\cf-ui.err.log")) {
        $m = Select-String -Path "$logDir\cf-ui.err.log" -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
        if ($m) { $uiUrl = $m.Matches[0].Value }
    }
    if ($apiUrl -and $uiUrl) { break }
}

if ($apiUrl -and $uiUrl) {
    Write-Host "`n--------------------------------------------------" -ForegroundColor Cyan
    Write-Host " Public UI    $uiUrl"
    Write-Host " Public API   $apiUrl"
    Write-Host "--------------------------------------------------" -ForegroundColor Cyan
    Write-Warn "anonymous quick tunnels: no auth in front of either URL, no uptime guarantee, and they'll change on the next run - anyone with the link can spend your real NREL API key. Stop with scripts\stop-all.ps1 when you're done demoing."
} else {
    Write-Err "tunnel URL(s) did not appear in time - check scripts\logs\cf-api.err.log and cf-ui.err.log"
    exit 1
}
