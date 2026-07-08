# Shared helpers for scripts\*.ps1 - dot-source this, don't run it directly:
#   . "$PSScriptRoot\common.ps1"
#
# Uses curl.exe (not Invoke-WebRequest/Invoke-RestMethod) for every health check.
# On this project's dev machines, Invoke-WebRequest has intermittently failed
# against services that curl.exe reaches fine on the same host/port in the same
# second - cause unconfirmed, but curl.exe has been reliable every time, so it's
# the only HTTP client used across these scripts.
#
# Plain ASCII only in every scripts\*.ps1 file, including comments and strings:
# Windows PowerShell 5.1 does not reliably read .ps1 files as UTF-8 without a BOM,
# so a stray em-dash or curly quote can silently corrupt into garbage bytes and
# break parsing (seen firsthand while writing this file).

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    OK   $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    WARN $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "    FAIL $msg" -ForegroundColor Red }

function Wait-ForHttp {
    param(
        [Parameter(Mandatory)][string]$Url,
        [int]$TimeoutSeconds = 40,
        [int]$IntervalSeconds = 2
    )
    $attempts = [math]::Max(1, [math]::Ceiling($TimeoutSeconds / $IntervalSeconds))
    for ($i = 0; $i -lt $attempts; $i++) {
        $code = curl.exe -s -o NUL -w "%{http_code}" --max-time 3 $Url 2>$null
        if ($code -eq "200") { return $true }
        Start-Sleep -Seconds $IntervalSeconds
    }
    return $false
}

function Test-PortListening {
    param([Parameter(Mandatory)][int]$Port)
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Stop-PortListener {
    param([Parameter(Mandatory)][int]$Port)
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        Write-Warn "stopping existing process on port $Port (PID $($c.OwningProcess))"
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    if ($conns) { Start-Sleep -Seconds 1 }
}

# Launches FilePath as a detached, hidden background process with stdout/stderr
# redirected to scripts\logs\<Name>.{out,err}.log, and returns the Process object.
function Start-Logged {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string]$LogDir
    )
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $out = Join-Path $LogDir "$Name.out.log"
    $err = Join-Path $LogDir "$Name.err.log"
    return Start-Process -FilePath $FilePath -ArgumentList $ArgumentList `
        -RedirectStandardOutput $out -RedirectStandardError $err `
        -WindowStyle Hidden -WorkingDirectory $WorkingDirectory -PassThru
}
