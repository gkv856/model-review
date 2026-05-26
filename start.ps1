# start.ps1 — starts backend (uvicorn) and frontend (npm run dev) in separate windows
# Run from repo root: .\start.ps1

$root = $PSScriptRoot

Write-Host "Starting Financial Model Integrity Reviewer..." -ForegroundColor Cyan
Write-Host ""

# ── Backend ───────────────────────────────────────────────────────────────────
$backendDir  = Join-Path $root "backend"
$uvicorn     = Join-Path $backendDir ".venv\Scripts\uvicorn.exe"

if (-not (Test-Path $uvicorn)) {
    Write-Host "[ERROR] Backend venv not found at $uvicorn" -ForegroundColor Red
    Write-Host "        Run: cd backend && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt"
    exit 1
}

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$backendDir'; Write-Host 'Backend starting on http://localhost:8000' -ForegroundColor Green; & '$uvicorn' main:app --reload --port 8000"
) -WindowStyle Normal

# ── Frontend ──────────────────────────────────────────────────────────────────
$frontendDir = Join-Path $root "frontend"
$nodeModules = Join-Path $frontendDir "node_modules"

if (-not (Test-Path $nodeModules)) {
    Write-Host "[ERROR] node_modules not found at $frontendDir" -ForegroundColor Red
    Write-Host "        Run: cd frontend && npm install"
    exit 1
}

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$frontendDir'; Write-Host 'Frontend starting on http://localhost:3000' -ForegroundColor Green; npm run dev"
) -WindowStyle Normal

Write-Host "Both servers launched in separate windows." -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend  →  http://localhost:8000" -ForegroundColor Yellow
Write-Host "  Frontend →  http://localhost:3000" -ForegroundColor Yellow
Write-Host ""
Write-Host "Close the individual windows to stop each server."
