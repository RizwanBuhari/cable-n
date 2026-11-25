# Starts the API (http://localhost:8000) and the website dev server (http://localhost:5173).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
foreach ($port in 8000, 5173) {
  if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "Port $port is already in use. Stop the program using it (or run .\scripts\stop.ps1 if it is Cable-N) and retry." -ForegroundColor Red; exit 1
  }
}
$api = Start-Process -PassThru -WindowStyle Minimized -FilePath "$root\backend\.venv\Scripts\python.exe" -ArgumentList '-m','uvicorn','app.main:app','--port','8000','--reload' -WorkingDirectory "$root\backend"
$web = Start-Process -PassThru -WindowStyle Minimized -FilePath 'cmd.exe' -ArgumentList '/c','npm run dev' -WorkingDirectory "$root\frontend"
"$($api.Id) $($web.Id)" | Set-Content "$root\.cablen.pids"
Write-Host 'Website:  http://localhost:5173'
Write-Host 'API docs: http://localhost:8000/api/docs'
Write-Host 'Stop with .\scripts\stop.ps1'
