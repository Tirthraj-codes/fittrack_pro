# Starts FitTrack Pro so phones on the same Wi-Fi or hotspot can open it.
Set-Location $PSScriptRoot

$python = ".\venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Virtual environment not found. Follow the README first." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

$port = 8000
$addresses = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -match '^(192\.168|10\.|172\.(1[6-9]|2[0-9]|3[01]))\.' -and
                   $_.InterfaceAlias -notmatch 'vEthernet|Loopback|VirtualBox|VMware|WSL|Bluetooth' } |
    Select-Object -ExpandProperty IPAddress

$env:DJANGO_ALLOWED_HOSTS = '*'
if ($addresses) { $env:SITE_URL = "http://$($addresses | Select-Object -First 1):$port" }

Write-Host ""
Write-Host "  FitTrack Pro demo server" -ForegroundColor Magenta
Write-Host "  On this laptop : http://127.0.0.1:$port"
foreach ($ip in $addresses) { Write-Host "  On your phone  : http://${ip}:$port" -ForegroundColor Green }
if (-not $addresses) { Write-Host "  No Wi-Fi or hotspot address found. Connect to the network first." -ForegroundColor Yellow }
Write-Host ""
Write-Host "  Keep this window open. Press Ctrl+C to stop."
Write-Host ""
& $python manage.py migrate --noinput | Out-Null
& $python manage.py runserver "0.0.0.0:$port"