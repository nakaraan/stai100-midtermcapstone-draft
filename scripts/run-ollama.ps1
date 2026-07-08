# LLM endpoint (:11434). Meant to be run in its own terminal window - for a
# scripted/backgrounded launch use run-all.ps1.
#
# Checks readiness with curl.exe rather than Invoke-RestMethod: the latter has
# intermittently misreported services as unreachable on this project's dev
# machines even while curl.exe reached them fine on the same host/port in the
# same second, which previously made this script try `ollama serve` against an
# already-bound port and fail.
. "$PSScriptRoot\common.ps1"

$tags = curl.exe -s --max-time 3 http://localhost:11434/api/tags 2>$null
if ($tags) {
    Write-Ok "Ollama is already running on :11434 - nothing to do, closing this window in 5s."
    Start-Sleep -Seconds 5
} else {
    ollama serve
}
