# FastAPI backend (:8000), --reload'd for active development. Meant to be run in
# its own terminal window - for a scripted/backgrounded launch use run-all.ps1.
#
# -Model optionally overwrites LLM_MODEL in .env before starting (e.g.
#   powershell -File scripts\run-api.ps1 -Model qwen2.5:7b
# ). Settings are cached per-process (config/settings.py's @lru_cache), so
# picking up a new model always means a fresh process, never just an edit to
# .env - this script always starts a new one rather than trying to detect and
# reuse an existing one the way run-all.ps1's orchestration does.
param(
    [string]$Model = $null
)
. "$PSScriptRoot\common.ps1"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if ($Model) {
    $envPath = "$root\.env"
    (Get-Content $envPath) -replace '^LLM_MODEL=.*', "LLM_MODEL=$Model" | Set-Content $envPath
    Write-Ok "set LLM_MODEL=$Model in .env"
}

if (Test-PortListening 8000) {
    Write-Warn "something is already listening on :8000 - stopping it first"
    Stop-PortListener 8000
}

& "$root\.venv\Scripts\python.exe" -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
