# Launches MLflow, Ollama (skipped if already running), the FastAPI backend,
# and the Streamlit UI, each in its own PowerShell window.
# Run from anywhere: powershell -File scripts\run-all.ps1

$root = Split-Path -Parent $PSScriptRoot

Start-Process powershell -ArgumentList "-NoExit", "-File", "$root\scripts\run-mlflow.ps1"
Start-Sleep -Seconds 3

Start-Process powershell -ArgumentList "-NoExit", "-File", "$root\scripts\run-ollama.ps1"
Start-Sleep -Seconds 2

Start-Process powershell -ArgumentList "-NoExit", "-File", "$root\scripts\run-api.ps1"
Start-Sleep -Seconds 2

Start-Process powershell -ArgumentList "-NoExit", "-File", "$root\scripts\run-ui.ps1"

Write-Host "Launched 4 windows: MLflow (:5000), Ollama (:11434), API (:8000), UI (:8501)."
Write-Host "Open http://localhost:8501 once the UI window says 'You can now view your Streamlit app'."
