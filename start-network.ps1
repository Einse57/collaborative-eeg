# Start EEG Annotation Platform with Network Access
# This script starts both backend and frontend servers configured for local network access

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  EEG/MEG Annotation Platform - Network Mode" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# Get the script's directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

# Get network IP address
Write-Host "Detecting network IP address..." -ForegroundColor Yellow
$networkIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
    $_.InterfaceAlias -eq 'Wi-Fi' -or 
    ($_.InterfaceAlias -like '*Ethernet*' -and $_.IPAddress -notlike '169.254.*')
} | Select-Object -First 1).IPAddress

if ($networkIP) {
    Write-Host "Network IP detected: $networkIP" -ForegroundColor Green
    Write-Host ""
    Write-Host "Users on your network can access the platform at:" -ForegroundColor Yellow
    Write-Host "  http://${networkIP}:3000" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "Warning: Could not detect network IP. Using localhost only." -ForegroundColor Yellow
    Write-Host ""
}

# Check if firewall rules exist
Write-Host "Checking firewall configuration..." -ForegroundColor Yellow
$firewallRules = Get-NetFirewallRule -DisplayName "EEG Platform*" -ErrorAction SilentlyContinue

if ($firewallRules) {
    Write-Host "Firewall rules found: OK" -ForegroundColor Green
} else {
    Write-Host "WARNING: Firewall rules not configured!" -ForegroundColor Red
    Write-Host "Network access may be blocked by Windows Firewall." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To configure firewall, run as Administrator:" -ForegroundColor Yellow
    Write-Host "  .\configure-firewall.ps1" -ForegroundColor Cyan
    Write-Host ""
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne 'y') {
        Write-Host "Exiting..." -ForegroundColor Yellow
        exit
    }
}

Write-Host ""
Write-Host "Starting servers..." -ForegroundColor Yellow
Write-Host ""

# Start Backend Server
Write-Host "Starting Backend Server (Port 8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$scriptPath\backend'; .\venv\Scripts\Activate.ps1; Write-Host 'Backend Server - Network Mode' -ForegroundColor Green; Write-Host 'Listening on http://0.0.0.0:8000' -ForegroundColor Yellow; Write-Host 'Network URL: http://${networkIP}:8000' -ForegroundColor Green; Write-Host ''; uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload"
)

# Wait a moment for backend to start
Start-Sleep -Seconds 2

# Start Frontend Server
Write-Host "Starting Frontend Server (Port 3000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$scriptPath\frontend'; Write-Host 'Frontend Server - Network Mode' -ForegroundColor Green; Write-Host 'Starting with --host flag for network access...' -ForegroundColor Yellow; Write-Host ''; npm run dev -- --host"
)

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "  Servers Starting!" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Local Access:" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""

if ($networkIP) {
    Write-Host "Network Access (Share this with collaborators):" -ForegroundColor Cyan
    Write-Host "  Frontend: http://${networkIP}:3000" -ForegroundColor Green
    Write-Host "  Backend:  http://${networkIP}:8000" -ForegroundColor Green
    Write-Host "  API Docs: http://${networkIP}:8000/docs" -ForegroundColor Green
    Write-Host ""
}

Write-Host "Note: Both servers will open in new PowerShell windows" -ForegroundColor Yellow
Write-Host "Close those windows to stop the servers" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press any key to exit this window..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
