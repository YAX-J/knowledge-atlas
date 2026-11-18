param(
    [int]$ApiPort = 8001,
    [int]$FrontendPort = 5174,
    [switch]$Seed
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$backendDir = Join-Path $repoRoot 'backend'
$frontendDir = Join-Path $repoRoot 'frontend'
$backendPython = Join-Path $backendDir '.venv\Scripts\python.exe'
$viteEntry = Join-Path $frontendDir 'node_modules\vite\bin\vite.js'
if (!(Test-Path -LiteralPath $backendPython) -or !(Test-Path -LiteralPath $viteEntry)) {
    throw 'Install backend .venv and run frontend npm ci first; see docs/DEMO.zh-CN.md.'
}
if ($ApiPort -eq $FrontendPort -or $ApiPort -lt 1024 -or $ApiPort -gt 65535 -or $FrontendPort -lt 1024 -or $FrontendPort -gt 65535) {
    throw 'Choose two different ports in 1024..65535.'
}
foreach ($port in @($ApiPort, $FrontendPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Port $port is occupied; no existing process will be stopped. Choose another port."
    }
}
$runDir = Join-Path $repoRoot ('output\demo-native\' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $runDir | Out-Null
$started = @()
$previousCors = $env:CORS_ORIGINS
$previousApi = $env:VITE_API_BASE_URL
$previousSource = $env:VITE_DATA_SOURCE
try {
    Push-Location $backendDir
    try {
        & $backendPython -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw 'Database migration failed; check native PostgreSQL and backend/.env.' }
        if ($Seed) {
            & $backendPython -m scripts.prepare_evaluation --dataset ..\evaluation --output-dir (Join-Path $runDir 'preparation') --accept-curated-fixture
            if ($LASTEXITCODE -ne 0) { throw 'Synthetic project initialization failed.' }
        }
    } finally { Pop-Location }
    $env:CORS_ORIGINS = '["http://127.0.0.1:' + $FrontendPort + '"]'
    $env:VITE_API_BASE_URL = 'http://127.0.0.1:' + $ApiPort + '/api/v1'
    $env:VITE_DATA_SOURCE = 'graph'
    $started += Start-Process -FilePath $backendPython -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', $ApiPort) -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runDir 'api.log') -RedirectStandardError (Join-Path $runDir 'api-error.log')
    $started += Start-Process -FilePath $backendPython -ArgumentList @('-m', 'app.worker') -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runDir 'worker.log') -RedirectStandardError (Join-Path $runDir 'worker-error.log')
    $started += Start-Process -FilePath $backendPython -ArgumentList @('-m', 'app.assistant_runner') -WorkingDirectory $backendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runDir 'assistant.log') -RedirectStandardError (Join-Path $runDir 'assistant-error.log')
    $nodeExecutable = (Get-Command node -ErrorAction Stop).Source
    $started += Start-Process -FilePath $nodeExecutable -ArgumentList @(('"' + $viteEntry + '"'), '--host', '127.0.0.1', '--port', $FrontendPort, '--strictPort') -WorkingDirectory $frontendDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runDir 'frontend.log') -RedirectStandardError (Join-Path $runDir 'frontend-error.log')
    $deadline = (Get-Date).AddSeconds(30)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        if ($started | Where-Object { $_.HasExited }) { throw "A demo process exited; inspect $runDir" }
        try {
            $null = Invoke-RestMethod -Uri ('http://127.0.0.1:' + $ApiPort + '/api/v1/health/ready') -TimeoutSec 2
            $null = Invoke-WebRequest -Uri ('http://127.0.0.1:' + $FrontendPort) -TimeoutSec 2
            $ready = $true
            break
        } catch { Start-Sleep -Milliseconds 300 }
    }
    if (!$ready) { throw "Readiness timed out; inspect $runDir" }
    Write-Host "Demo ready: http://127.0.0.1:$FrontendPort ; API: http://127.0.0.1:$ApiPort/docs"
    Write-Host "Logs: $runDir ; Ctrl+C stops only this launcher's processes. No model calls are automatic."
    while ($true) {
        if ($started | Where-Object { $_.HasExited }) { throw "A demo process exited; inspect $runDir" }
        Start-Sleep -Seconds 1
    }
} finally {
    foreach ($process in $started) {
        if (!$process.HasExited) { $process.Kill(); $process.WaitForExit(5000) | Out-Null }
    }
    $env:CORS_ORIGINS = $previousCors
    $env:VITE_API_BASE_URL = $previousApi
    $env:VITE_DATA_SOURCE = $previousSource
}
