# dev.ps1 - start the backend (uvicorn) and frontend (Vite) together.
# Native Windows PowerShell. Run with:  .\dev.ps1

$ErrorActionPreference = 'Stop'

$Root          = $PSScriptRoot
$BackendDir    = Join-Path $Root 'backend'
$FrontendDir   = Join-Path $Root 'frontend'
$BackendPort   = 8000
$FrontendPort  = 5173
$BackendUrl    = "http://localhost:$BackendPort"
$FrontendUrl   = "http://localhost:$FrontendPort"

function Write-Step  { Write-Host ""; Write-Host "==> $args" -ForegroundColor Cyan }
function Write-Ok    { Write-Host "    $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "    WARNING: $args" -ForegroundColor Yellow }
function Write-Err   { Write-Host "    ERROR: $args" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# Backend: locate or create a venv, install deps, ensure .env
# ---------------------------------------------------------------------------
$pyCandidates = @(
  (Join-Path $BackendDir '.venv\Scripts\python.exe'),
  (Join-Path $BackendDir '.venv\bin\python')
)
$Python = $pyCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $Python) {
  Write-Step 'No backend venv found. Creating backend\.venv ...'
  Push-Location $BackendDir
  try {
    if (Get-Command uv -ErrorAction SilentlyContinue) { uv venv }
    else { python -m venv .venv }
  } finally { Pop-Location }
  $Python = $pyCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

if (-not $Python) {
  Write-Err 'Could not create a Python venv. Install Python 3.10+ or uv first.'
  exit 1
}

& $Python -c 'import fastapi, uvicorn, pydantic' 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Step 'Installing backend dependencies (this may take a while)...'
  & $Python -m pip install --upgrade pip | Out-Null
  & $Python -m pip install -r (Join-Path $BackendDir 'requirements.txt')
}

if (-not (Test-Path -LiteralPath (Join-Path $BackendDir '.env'))) {
  Copy-Item (Join-Path $BackendDir '.env.example') (Join-Path $BackendDir '.env')
  Write-Ok 'Created backend\.env from backend\.env.example'
}

# ---------------------------------------------------------------------------
# Frontend: ensure npm and node_modules
# ---------------------------------------------------------------------------
$Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $Npm) { $Npm = Get-Command npm -ErrorAction SilentlyContinue }
if (-not $Npm) {
  Write-Err 'npm not found. Install Node.js 20+ first.'
  exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir 'node_modules'))) {
  Write-Step 'Installing frontend dependencies...'
  Push-Location $FrontendDir
  try { & $Npm.Source install } finally { Pop-Location }
}

# ---------------------------------------------------------------------------
# Port conflict check
# ---------------------------------------------------------------------------
try {
  $null = Invoke-WebRequest -Uri "$BackendUrl/health" -UseBasicParsing -TimeoutSec 2
  Write-Warn "Something is already listening on port $BackendPort."
} catch { }
try {
  $null = Invoke-WebRequest -Uri $FrontendUrl -UseBasicParsing -TimeoutSec 2
  Write-Warn "Something is already listening on port $FrontendPort."
} catch { }

# ---------------------------------------------------------------------------
# Start servers
# ---------------------------------------------------------------------------
$BackendLog  = Join-Path $BackendDir 'backend.log'
$BackendErr  = Join-Path $BackendDir 'backend.err.log'
$FrontendLog = Join-Path $FrontendDir 'frontend.log'
$FrontendErr = Join-Path $FrontendDir 'frontend.err.log'

Write-Step "Starting backend (uvicorn) on $BackendUrl"
$Backend = Start-Process -FilePath $Python `
  -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort", '--reload') `
  -WorkingDirectory $BackendDir `
  -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErr `
  -WindowStyle Hidden -PassThru

Write-Step "Starting frontend (Vite) on $FrontendUrl"
$Frontend = Start-Process -FilePath $Npm.Source `
  -ArgumentList @('run', 'dev') `
  -WorkingDirectory $FrontendDir `
  -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErr `
  -WindowStyle Hidden -PassThru

# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------
function Wait-Health($Name, $Url) {
  Write-Host "    Waiting for $Name ..." -NoNewline
  for ($i = 0; $i -lt 60; $i++) {
    try {
      $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -lt 500) {
        Write-Host ' ready' -ForegroundColor Green
        return $true
      }
    } catch { }
    Start-Sleep -Seconds 1
  }
  Write-Host ' NOT ready after 60s' -ForegroundColor Yellow
  return $false
}

$null = Wait-Health 'backend' "$BackendUrl/health"
$null = Wait-Health 'frontend' $FrontendUrl

# ---------------------------------------------------------------------------
# Open the browser and keep running
# ---------------------------------------------------------------------------
Start-Process $FrontendUrl

Write-Ok ''
Write-Ok "Backend:  $BackendUrl  (log: backend/backend.log)"
Write-Ok "Frontend: $FrontendUrl (log: frontend/frontend.log)"
Write-Ok 'Press Ctrl+C to stop both servers.'

try {
  while (-not $Backend.HasExited -and -not $Frontend.HasExited) { Start-Sleep -Seconds 1 }
  Write-Ok 'A server exited; shutting down the other...'
} finally {
  Write-Step 'Stopping servers...'
  foreach ($p in @($Backend, $Frontend)) {
    if ($p -and -not $p.HasExited) {
      & taskkill.exe /PID $p.Id /T /F 2>$null | Out-Null
    }
  }
}
