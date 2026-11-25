# Stops only the processes started by start.ps1 (and their children).
$root = Split-Path -Parent $PSScriptRoot
$f = "$root\.cablen.pids"
if (-not (Test-Path $f)) { Write-Host 'Nothing to stop (no .cablen.pids).'; exit 0 }
foreach ($id in (Get-Content $f).Split(' ')) { if ($id) { & taskkill /PID $id /T /F 2>$null | Out-Null } }
Remove-Item $f
Write-Host 'Cable-N stopped.'
