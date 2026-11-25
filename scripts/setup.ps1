# Cable-N local setup (Windows PowerShell). Safe to re-run. No admin rights needed.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
function Need($cmd, $hint) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Write-Host "Missing: $cmd - $hint" -ForegroundColor Red; exit 1 } }
Need python 'install Python 3.11+ from https://www.python.org/downloads/ (tick "Add to PATH")'
Need node 'install Node.js 20+ LTS from https://nodejs.org/'
Need npm 'comes with Node.js'
Write-Host "Python: $(python --version)  Node: $(node --version)"

if (-not (Test-Path backend\.venv)) { python -m venv backend\.venv }
& backend\.venv\Scripts\python.exe -m pip install --upgrade pip -q
& backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt -q
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env; Write-Host 'Created backend\.env (edit it for optional AI / licence settings).' }
if (-not (Test-Path frontend\.env.local)) { Copy-Item frontend\.env.example frontend\.env.local; Write-Host 'Created frontend\.env.local (edit it for AdSense / site URL).' }
Push-Location frontend; npm install --no-audit --no-fund; Pop-Location
Write-Host "`nSetup complete. Start with: .\scripts\start.ps1" -ForegroundColor Green
Write-Host 'No database or administrator account is needed - Cable-N is a public, stateless site.'
