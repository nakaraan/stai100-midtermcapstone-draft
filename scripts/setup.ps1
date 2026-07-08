# One-time (but safe-to-re-run) environment setup: venv, dependencies, .env, Ollama models.
# Covers exactly the commands in README's "One-time setup", made idempotent.
#
#   powershell -File scripts\setup.ps1
#   powershell -File scripts\setup.ps1 -Force   # rebuild .venv even if it looks valid
#
# Deliberately never calls .venv\Scripts\Activate.ps1 - every command below invokes
# .venv\Scripts\python.exe directly by path instead. That sidesteps PowerShell's
# execution-policy prompt entirely (activation is the only step that needs it) and
# means this script has no per-window state to lose, unlike activation.
param(
    [switch]$Force
)

. "$PSScriptRoot\common.ps1"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

Write-Step "Python virtual environment (.venv)"
# Only (re)created when actually broken/missing, or with -Force. .venv may ship
# committed to this repo from a previous machine (see README) with a python.exe
# that won't run here at all - but if run-all.ps1's services are currently up,
# THIS machine's own .venv\Scripts\python.exe is a locked, running executable,
# and unconditionally recreating it fails with "Unable to copy ... python.exe"
# (harmless in practice, since venv leaves the working existing file in place -
# but alarming to see, so avoid it whenever the venv already works).
$needsVenv = $Force -or -not (Test-Path $venvPython)
if (-not $needsVenv) {
    & $venvPython -m pip --version *> $null
    $needsVenv = $LASTEXITCODE -ne 0
}
if ($needsVenv) {
    python -m venv "$root\.venv"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
        Write-Err "venv creation failed - is Python 3.11+ installed and on PATH?"
        exit 1
    }
    Write-Ok "created ($((& $venvPython --version)))"
} else {
    Write-Ok "already valid on this machine ($((& $venvPython --version))) - not touching it"
}

Write-Step "Python dependencies"
& $venvPython -m pip install --disable-pip-version-check -r "$root\requirements.txt"
if ($LASTEXITCODE -ne 0) { Write-Err "pip install -r requirements.txt failed"; exit 1 }
& $venvPython -m pip install --disable-pip-version-check mlflow
if ($LASTEXITCODE -ne 0) { Write-Err "pip install mlflow failed"; exit 1 }
Write-Ok "requirements.txt + full mlflow package installed"

Write-Step ".env"
$envPath = Join-Path $root ".env"
if (-not (Test-Path $envPath)) {
    Copy-Item "$root\.env.example" $envPath
    Write-Err "Created .env from .env.example - open it, fill in NREL_API_KEY / NREL_API_EMAIL, then re-run this script."
    exit 1
}
$envContent = Get-Content $envPath -Raw
if ($envContent -match "your-nrel-api-key" -or $envContent -match "you@example\.com") {
    Write-Err ".env still has placeholder NREL_API_KEY/NREL_API_EMAIL - fill in real values, then re-run this script."
    exit 1
}
Write-Ok "present and filled in"

Write-Step "Ollama models"
$tags = curl.exe -s --max-time 5 http://localhost:11434/api/tags 2>$null
if (-not $tags) {
    Write-Err "Ollama isn't reachable on :11434 - install/start Ollama (https://ollama.com), then re-run this script."
    exit 1
}
foreach ($model in @("llama3.2:3b", "qwen2.5:7b")) {
    if ($tags -match [regex]::Escape($model)) {
        Write-Ok "$model already pulled"
    } else {
        Write-Warn "pulling $model (this can take a while the first time)..."
        ollama pull $model
        if ($LASTEXITCODE -ne 0) { Write-Err "ollama pull $model failed"; exit 1 }
        Write-Ok "$model pulled"
        $tags = curl.exe -s --max-time 5 http://localhost:11434/api/tags 2>$null
    }
}

Write-Host "`nSetup complete. Next: powershell -File scripts\run-all.ps1" -ForegroundColor Cyan
