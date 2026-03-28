param(
    [string]$BackendHost = "127.0.0.1",
    [int]$BackendPort = 8000,
    [string]$FrontendHost = "127.0.0.1",
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $frontendDir)) {
    throw "Frontend directory not found: $frontendDir"
}

if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonExe = "python"
}

$backendCommand = @"
Set-Location '$repoRoot'
`$env:PYTHONPATH = '$repoRoot'
& '$pythonExe' -m uvicorn backend.app:app --reload --host $BackendHost --port $BackendPort
"@

$frontendCommand = @"
Set-Location '$frontendDir'
& npm.cmd run dev -- --host $FrontendHost --port $FrontendPort
"@

Write-Host "Starting TeachWithMeAI backend on http://$BackendHost`:$BackendPort" -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    $backendCommand
)

Write-Host "Starting TeachWithMeAI frontend on http://$FrontendHost`:$FrontendPort" -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    $frontendCommand
)

Write-Host ""
Write-Host "Launched both dev servers in separate PowerShell windows." -ForegroundColor Yellow
Write-Host "Frontend: http://$FrontendHost`:$FrontendPort"
Write-Host "Backend:  http://$BackendHost`:$BackendPort"
