try {
    Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 | Out-Null
    Write-Host "Ollama is already running on :11434 - nothing to do, closing this window in 5s."
    Start-Sleep -Seconds 5
} catch {
    ollama serve
}
