# Stops everything started by run-all.ps1 / run-tunnel.ps1: MLflow, API, UI, and
# any cloudflared tunnels. Leaves Ollama running, since README treats it as a
# persistent background service rather than something to cycle per-demo - stop it
# yourself (Task Manager, or `ollama stop`/quit the tray app) if you want it down too.
. "$PSScriptRoot\common.ps1"

Write-Step "Stopping AGENT P services"
foreach ($port in 8501, 8000, 5000) {
    if (Test-PortListening $port) {
        Stop-PortListener $port
        Write-Ok "stopped process on :$port"
    } else {
        Write-Ok ":$port already clear"
    }
}

Write-Step "Stopping Cloudflare tunnels"
$cf = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($cf) {
    $cf | Stop-Process -Force
    Write-Ok "stopped $($cf.Count) cloudflared process(es)"
} else {
    Write-Ok "none running"
}

Write-Host "`nDone. Ollama left running (:11434) - it's a shared service, not stopped by this script." -ForegroundColor Cyan
