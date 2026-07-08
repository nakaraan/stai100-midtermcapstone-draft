# Single-command launch: MLflow -> Ollama -> API -> UI, each started detached and
# health-polled before moving to the next (MLflow must be confirmed up before
# anything else touches it - every traced call otherwise hangs retrying against a
# closed port). Safe to re-run: every step checks whether it's already up first,
# so re-running just confirms a healthy stack instead of erroring on bound ports.
#
#   powershell -File scripts\run-all.ps1                     # defaults to qwen2.5:7b
#   powershell -File scripts\run-all.ps1 -Model llama3.2:3b
#   powershell -File scripts\run-all.ps1 -Tunnel              # + public Cloudflare URLs
#
# Logs for every service land in scripts\logs\<name>.{out,err}.log.
param(
    [ValidateSet("llama3.2:3b", "qwen2.5:7b")]
    [string]$Model = "qwen2.5:7b",
    [switch]$Tunnel
)

. "$PSScriptRoot\common.ps1"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$logDir = Join-Path $root "scripts\logs"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$envPath = Join-Path $root ".env"

if (-not (Test-Path $venvPython)) {
    Write-Err ".venv not found - run: powershell -File scripts\setup.ps1"
    exit 1
}
if (-not (Test-Path $envPath)) {
    Write-Err ".env not found - run: powershell -File scripts\setup.ps1"
    exit 1
}

Write-Step "MLflow (:5000)"
if (Test-PortListening 5000) {
    Write-Ok "already running"
} else {
    Start-Logged -FilePath $venvPython -WorkingDirectory $root -LogDir $logDir -Name "mlflow" -ArgumentList @(
        "-m", "mlflow", "server", "--host", "0.0.0.0", "--port", "5000",
        "--backend-store-uri", "sqlite:///.mlflow/mlflow.db"
    ) | Out-Null
    if (Wait-ForHttp -Url "http://localhost:5000" -TimeoutSeconds 40) {
        Write-Ok "up"
    } else {
        Write-Err "did not come up in time - check scripts\logs\mlflow.err.log"
        exit 1
    }
}

Write-Step "Ollama (:11434)"
$tags = curl.exe -s --max-time 3 http://localhost:11434/api/tags 2>$null
if ($tags) {
    Write-Ok "already running"
} else {
    Start-Logged -FilePath "ollama" -WorkingDirectory $root -LogDir $logDir -Name "ollama" -ArgumentList @("serve") | Out-Null
    if (Wait-ForHttp -Url "http://localhost:11434/api/tags" -TimeoutSeconds 20) {
        Write-Ok "up"
    } else {
        Write-Err "did not come up in time - check scripts\logs\ollama.err.log"
        exit 1
    }
    $tags = curl.exe -s --max-time 3 http://localhost:11434/api/tags 2>$null
}
if ($tags -notmatch [regex]::Escape($Model)) {
    Write-Err "$Model isn't pulled yet - run: powershell -File scripts\setup.ps1"
    exit 1
}
Write-Ok "$Model available"

Write-Step "API (:8000) with LLM_MODEL=$Model"
$currentModelLine = (Get-Content $envPath | Where-Object { $_ -match '^LLM_MODEL=' } | Select-Object -First 1)
if ($currentModelLine) { $currentModelLine = $currentModelLine.Trim() }
$modelChanged = $currentModelLine -ne "LLM_MODEL=$Model"
if ($modelChanged) {
    (Get-Content $envPath) -replace '^LLM_MODEL=.*', "LLM_MODEL=$Model" | Set-Content $envPath
    Write-Warn "updated .env: LLM_MODEL -> $Model"
}
if ($modelChanged -or -not (Test-PortListening 8000)) {
    # A running API process cached the old model at import time (settings are
    # @lru_cache'd) - editing .env alone would do nothing until it restarts.
    Stop-PortListener 8000
    Start-Logged -FilePath $venvPython -WorkingDirectory $root -LogDir $logDir -Name "api" -ArgumentList @(
        "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"
    ) | Out-Null
    if (Wait-ForHttp -Url "http://localhost:8000/health" -TimeoutSeconds 30) {
        Write-Ok "up"
    } else {
        Write-Err "did not come up in time - check scripts\logs\api.err.log"
        exit 1
    }
} else {
    Write-Ok "already running with the right model"
}

Write-Step "Streamlit UI (:8501)"
if (Test-PortListening 8501) {
    Write-Ok "already running"
} else {
    Start-Logged -FilePath $venvPython -WorkingDirectory $root -LogDir $logDir -Name "ui" -ArgumentList @(
        "-m", "streamlit", "run", "app/ui.py", "--server.port", "8501", "--server.headless", "true"
    ) | Out-Null
    if (Wait-ForHttp -Url "http://localhost:8501" -TimeoutSeconds 30) {
        Write-Ok "up"
    } else {
        Write-Err "did not come up in time - check scripts\logs\ui.err.log"
        exit 1
    }
}

Write-Host "`n--------------------------------------------------" -ForegroundColor Cyan
Write-Host " MLflow   http://localhost:5000"
Write-Host " API      http://localhost:8000  (docs at /docs)"
Write-Host " UI       http://localhost:8501"
Write-Host " Model    $Model"
Write-Host " Logs     scripts\logs\"
Write-Host "--------------------------------------------------" -ForegroundColor Cyan

if ($Tunnel) {
    & "$PSScriptRoot\run-tunnel.ps1"
}
