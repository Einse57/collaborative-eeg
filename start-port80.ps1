# EEG/MEG Annotation Platform - Port 80 Startup Script
# This version uses nginx to serve everything on port 80 (standard HTTP)
# Perfect for enterprise networks with strict firewall rules
#
# Prerequisites:
#   1. Download nginx for Windows from https://nginx.org/en/download.html
#   2. Extract to C:\nginx
#   3. Copy nginx.conf from this project to C:\nginx\conf\nginx.conf
#   4. Run this script as Administrator (required for port 80)
#
# Usage:
#   .\start-port80.ps1           - Start in local mode (localhost only)
#   .\start-port80.ps1 -Network  - Start in network mode (accessible from other devices)

param(
    [switch]$Network
)

# Check if running as Administrator (required for port 80)
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator to use port 80" -ForegroundColor Red
    Write-Host ""
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then run this script again." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Alternatively, use the regular start.ps1 script (uses ports 3000/8000):" -ForegroundColor Cyan
    Write-Host "  .\start.ps1" -ForegroundColor White
    exit 1
}

# Get the script's directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

# Check if nginx is installed
$nginxPath = "C:\nginx\nginx.exe"
if (-not (Test-Path $nginxPath)) {
    Write-Host "ERROR: nginx not found at $nginxPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install nginx:" -ForegroundColor Yellow
    Write-Host "  1. Download from https://nginx.org/en/download.html" -ForegroundColor White
    Write-Host "  2. Extract to C:\nginx" -ForegroundColor White
    Write-Host "  3. Run this script again (it will copy nginx.conf automatically)" -ForegroundColor White
    Write-Host ""
    Write-Host "Or use the regular start.ps1 script instead (no nginx required):" -ForegroundColor Cyan
    Write-Host "  .\start.ps1" -ForegroundColor White
    exit 1
}

# Copy nginx configuration from project to nginx installation
Write-Host "Configuring nginx..." -ForegroundColor Yellow
$nginxConfSource = Join-Path $scriptPath "nginx.conf"
$nginxConfDest = "C:\nginx\conf\nginx.conf"

if (Test-Path $nginxConfSource) {
    try {
        Copy-Item -Path $nginxConfSource -Destination $nginxConfDest -Force
        Write-Host "nginx configuration copied successfully" -ForegroundColor Green
    } catch {
        Write-Host "WARNING: Could not copy nginx.conf: $_" -ForegroundColor Yellow
        Write-Host "You may need to manually copy nginx.conf to C:\nginx\conf\nginx.conf" -ForegroundColor Yellow
    }
} else {
    Write-Host "WARNING: nginx.conf not found in project directory" -ForegroundColor Yellow
}

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  EEG/MEG Annotation Platform - Port 80 Mode" -ForegroundColor Cyan
Write-Host "  Enterprise Firewall Friendly" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Cyan
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
        Write-Host "  http://${networkIP}" -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Host "Warning: Could not detect network IP. Using localhost only." -ForegroundColor Yellow
        Write-Host ""
    }

    # Check if firewall rules exist
    Write-Host "Checking firewall configuration..." -ForegroundColor Yellow
    $firewallRule = Get-NetFirewallRule -DisplayName "EEG Platform Port 80" -ErrorAction SilentlyContinue

    if ($firewallRule) {
        Write-Host "Firewall rule found: OK" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Firewall rule not configured!" -ForegroundColor Red
        Write-Host "Network access may be blocked by Windows Firewall." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Creating firewall rule now..." -ForegroundColor Yellow
        
        try {
            New-NetFirewallRule -DisplayName "EEG Platform Port 80" `
                -Direction Inbound `
                -LocalPort 80 `
                -Protocol TCP `
                -Action Allow `
                -Profile Any `
                -Description "Allow HTTP access to EEG/MEG Annotation Platform on port 80"
            Write-Host "Firewall rule created successfully!" -ForegroundColor Green
        } catch {
            Write-Host "Failed to create firewall rule. Network access may not work." -ForegroundColor Red
        }
    }
    Write-Host ""
}

Write-Host "Starting backend server (internal port 8000)..." -ForegroundColor Yellow

# Start backend in a new PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptPath\backend'; Write-Host 'Backend Server' -ForegroundColor Green; Write-Host 'Internal: http://localhost:8000' -ForegroundColor Yellow; Write-Host 'Public access via nginx on port 80' -ForegroundColor Cyan; Write-Host ''; if (Test-Path '.\venv\Scripts\python.exe') { .\venv\Scripts\python.exe -m uvicorn app.main:socket_app --host 127.0.0.1 --port 8000 --reload } else { python -m uvicorn app.main:socket_app --host 127.0.0.1 --port 8000 --reload }"

Start-Sleep -Seconds 3

Write-Host "Starting frontend server (internal port 3000)..." -ForegroundColor Yellow

# Start frontend in a new PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptPath\frontend'; Write-Host 'Frontend Server' -ForegroundColor Green; Write-Host 'Internal: http://localhost:3000' -ForegroundColor Yellow; Write-Host 'Public access via nginx on port 80' -ForegroundColor Cyan; Write-Host ''; npm run dev"

Start-Sleep -Seconds 5

# Check if nginx is already running
$nginxProcess = Get-Process nginx -ErrorAction SilentlyContinue
if ($nginxProcess) {
    Write-Host "Stopping existing nginx process..." -ForegroundColor Yellow
    Stop-Process -Name nginx -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Write-Host "Starting nginx reverse proxy on port 80..." -ForegroundColor Yellow

# Start nginx in a new PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\nginx; Write-Host 'nginx Reverse Proxy' -ForegroundColor Green; Write-Host 'Serving on port 80 (HTTP)' -ForegroundColor Yellow; Write-Host ''; .\nginx.exe"

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "  Platform Running on Port 80!" -ForegroundColor Green
Write-Host "  Firewall Friendly Configuration" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Local Access:" -ForegroundColor Cyan
Write-Host "  Web App:  http://localhost" -ForegroundColor White
Write-Host "  API Docs: http://localhost/docs" -ForegroundColor White
Write-Host ""

if ($Network -and $networkIP) {
    Write-Host "Network Access (Share this with collaborators):" -ForegroundColor Cyan
    Write-Host "  Web App:  http://${networkIP}" -ForegroundColor Green
    Write-Host "  API Docs: http://${networkIP}/docs" -ForegroundColor Green
    Write-Host ""
}

Write-Host "Technical Details:" -ForegroundColor DarkGray
Write-Host "  - nginx (port 80) -> Frontend (port 3000)" -ForegroundColor DarkGray
Write-Host "  - nginx (port 80/api/) -> Backend (port 8000)" -ForegroundColor DarkGray
Write-Host "  - All traffic on standard HTTP port" -ForegroundColor DarkGray
Write-Host ""

Write-Host "Opening browser..." -ForegroundColor Green
Start-Sleep -Seconds 2
Start-Process "http://localhost"

Write-Host ""
Write-Host "To stop the servers:" -ForegroundColor Yellow
Write-Host "  1. Close the PowerShell windows (backend, frontend)" -ForegroundColor White
Write-Host "  2. Run: C:\nginx\nginx.exe -s stop" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit this window..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
