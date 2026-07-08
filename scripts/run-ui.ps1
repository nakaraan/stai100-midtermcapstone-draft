# Streamlit UI (:8501). Meant to be run in its own terminal window - for a
# scripted/backgrounded launch use run-all.ps1.
. "$PSScriptRoot\common.ps1"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (Test-PortListening 8501) {
    Write-Ok "UI is already running on :8501 - nothing to do."
    exit 0
}

& "$root\.venv\Scripts\python.exe" -m streamlit run app/ui.py --server.port 8501 --server.headless true
