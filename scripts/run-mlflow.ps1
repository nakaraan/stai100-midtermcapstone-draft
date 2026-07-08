# MLflow tracking server (:5000). Meant to be run in its own terminal window so
# you can watch its logs live - for a scripted/backgrounded launch use run-all.ps1.
. "$PSScriptRoot\common.ps1"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (Test-PortListening 5000) {
    Write-Ok "MLflow is already running on :5000 - nothing to do."
    exit 0
}

& "$root\.venv\Scripts\python.exe" -m mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:///.mlflow/mlflow.db
