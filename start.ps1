# EEG/MEG Annotation Platform - Startup Script
# This script starts both the backend and frontend servers
#
# Usage:
#   .\start.ps1           - Start in local mode (localhost only)
#   .\start.ps1 -Network  - Start in network mode (accessible from other devices)

param(
    [switch]$Network
)

# Get the script's directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($Network) {
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "  EEG/MEG Annotation Platform - Network Mode" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
} else {
    Write-Host "Starting EEG/MEG Annotation Platform..." -ForegroundColor Cyan
}

Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Python not found. Please install Python 3.9+" -ForegroundColor Red
    exit 1
}

# Check if Node.js is installed
try {
    $nodeVersion = node --version 2>&1
    Write-Host "Node.js found: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "Node.js not found. Please install Node.js 18+" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Network mode setup
if ($Network) {
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
}

Write-Host "Starting backend server..." -ForegroundColor Yellow

# Start backend in a new PowerShell window
# Use venv's python directly to ensure packages are available
if ($Network) {
    $backendTitle = "Backend Server - Network Mode"
    $backendInfo = "Write-Host '$backendTitle' -ForegroundColor Green; Write-Host 'Listening on http://0.0.0.0:8000' -ForegroundColor Yellow; if ('$networkIP') { Write-Host 'Network URL: http://${networkIP}:8000' -ForegroundColor Green }; Write-Host '';"
} else {
    $backendTitle = "Backend Server"
    $backendInfo = "Write-Host '$backendTitle' -ForegroundColor Green; Write-Host '';"
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptPath\backend'; $backendInfo if (Test-Path '.\venv\Scripts\python.exe') { .\venv\Scripts\python.exe -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload } else { python -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload }"

Start-Sleep -Seconds 3

Write-Host "Starting frontend server..." -ForegroundColor Yellow

# Start frontend in a new PowerShell window
if ($Network) {
    $frontendTitle = "Frontend Server - Network Mode"
    $frontendInfo = "Write-Host '$frontendTitle' -ForegroundColor Green; Write-Host 'Starting with --host flag for network access...' -ForegroundColor Yellow; Write-Host '';"
    $frontendCmd = "npm run dev -- --host"
} else {
    $frontendTitle = "Frontend Server"
    $frontendInfo = "Write-Host '$frontendTitle' -ForegroundColor Green; Write-Host '';"
    $frontendCmd = "npm run dev"
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptPath\frontend'; $frontendInfo $frontendCmd"

Write-Host ""
Write-Host "Application starting!" -ForegroundColor Green
Write-Host ""
Write-Host "Local Access:" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""

if ($Network -and $networkIP) {
    Write-Host "Network Access (Share this with collaborators):" -ForegroundColor Cyan
    Write-Host "  Frontend: http://${networkIP}:3000" -ForegroundColor Green
    Write-Host "  Backend:  http://${networkIP}:8000" -ForegroundColor Green
    Write-Host "  API Docs: http://${networkIP}:8000/docs" -ForegroundColor Green
    Write-Host ""
}

Write-Host "Waiting for servers to initialize..." -ForegroundColor Yellow

# Wait for backend to be ready (plugins loading, etc.)
Start-Sleep -Seconds 5

# Wait for frontend dev server to be ready
Start-Sleep -Seconds 3

Write-Host "Opening browser..." -ForegroundColor Green
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "Press Ctrl+C in each terminal window to stop the servers" -ForegroundColor Yellow
