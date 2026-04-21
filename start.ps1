# EEG/MEG Annotation Platform - Startup Script
# This script starts both the backend and frontend servers
#
# Usage:
#   .\start.ps1                    - Start in local mode (localhost only)
#   .\start.ps1 -Network           - Start in network mode (ports 3000/8000)
#   .\start.ps1 -Nginx             - Serve on port 80 via nginx (requires Admin)
#   .\start.ps1 -Network -Nginx    - Network mode on port 80 via nginx

param(
    [switch]$Network,
    [switch]$Nginx
)

# Get the script's directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- Nginx pre-flight checks ---
if ($Nginx) {
    # Require Administrator for port 80
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-Host "ERROR: -Nginx requires running as Administrator (port 80)" -ForegroundColor Red
        Write-Host ""
        Write-Host "Right-click PowerShell and select 'Run as Administrator', then run:" -ForegroundColor Yellow
        Write-Host "  .\start.ps1 -Nginx" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Or drop -Nginx to use ports 3000/8000 without admin:" -ForegroundColor Cyan
        Write-Host "  .\start.ps1 -Network" -ForegroundColor White
        exit 1
    }

    # Check nginx installation
    $nginxPath = "C:\nginx\nginx.exe"
    if (-not (Test-Path $nginxPath)) {
        Write-Host "ERROR: nginx not found at $nginxPath" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please install nginx:" -ForegroundColor Yellow
        Write-Host "  1. Download from https://nginx.org/en/download.html" -ForegroundColor White
        Write-Host "  2. Extract to C:\nginx" -ForegroundColor White
        Write-Host "  3. Run this script again" -ForegroundColor White
        Write-Host ""
        Write-Host "Or drop -Nginx to use ports 3000/8000 (no nginx required):" -ForegroundColor Cyan
        Write-Host "  .\start.ps1 -Network" -ForegroundColor White
        exit 1
    }

    # Copy nginx.conf
    Write-Host "Configuring nginx..." -ForegroundColor Yellow
    $nginxConfSource = Join-Path $scriptPath "nginx.conf"
    $nginxConfDest = "C:\nginx\conf\nginx.conf"
    if (Test-Path $nginxConfSource) {
        try {
            Copy-Item -Path $nginxConfSource -Destination $nginxConfDest -Force
            Write-Host "nginx configuration copied successfully" -ForegroundColor Green
        } catch {
            Write-Host "WARNING: Could not copy nginx.conf: $_" -ForegroundColor Yellow
        }
    } else {
        Write-Host "WARNING: nginx.conf not found in project directory" -ForegroundColor Yellow
    }
}

# --- Banner ---
if ($Nginx) {
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "  EEG/MEG Annotation Platform - Port 80 (nginx)" -ForegroundColor Cyan
    Write-Host "  Enterprise Firewall Friendly" -ForegroundColor Green
    Write-Host "===========================================================" -ForegroundColor Cyan
} elseif ($Network) {
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

# --- Network / firewall setup ---
if ($Network -or $Nginx) {
    Write-Host "Detecting network IP address..." -ForegroundColor Yellow
    $networkIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
        $_.InterfaceAlias -eq 'Wi-Fi' -or 
        ($_.InterfaceAlias -like '*Ethernet*' -and $_.IPAddress -notlike '169.254.*')
    } | Select-Object -First 1).IPAddress

    if ($networkIP) {
        Write-Host "Network IP detected: $networkIP" -ForegroundColor Green
        Write-Host ""
        if ($Nginx) {
            Write-Host "Users on your network can access the platform at:" -ForegroundColor Yellow
            Write-Host "  http://${networkIP}" -ForegroundColor Green
        } else {
            Write-Host "Users on your network can access the platform at:" -ForegroundColor Yellow
            Write-Host "  http://${networkIP}:3000" -ForegroundColor Green
        }
        Write-Host ""
    } else {
        Write-Host "Warning: Could not detect network IP. Using localhost only." -ForegroundColor Yellow
        Write-Host ""
    }

    # Firewall check
    Write-Host "Checking firewall configuration..." -ForegroundColor Yellow

    if ($Nginx) {
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
    } else {
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
    }
    Write-Host ""
}

# --- Start backend ---
Write-Host "Starting backend server..." -ForegroundColor Yellow

if ($Nginx) {
    # Nginx mode: bind to localhost only; nginx proxies from port 80
    $backendHost = "127.0.0.1"
    $backendInfo = "Write-Host 'Backend Server (nginx mode)' -ForegroundColor Green; Write-Host 'Internal: http://localhost:8000' -ForegroundColor Yellow; Write-Host 'Public access via nginx on port 80' -ForegroundColor Cyan; Write-Host '';"
} elseif ($Network) {
    $backendHost = "0.0.0.0"
    $backendInfo = "Write-Host 'Backend Server - Network Mode' -ForegroundColor Green; Write-Host 'Listening on http://0.0.0.0:8000' -ForegroundColor Yellow; if ('$networkIP') { Write-Host 'Network URL: http://${networkIP}:8000' -ForegroundColor Green }; Write-Host '';"
} else {
    $backendHost = "0.0.0.0"
    $backendInfo = "Write-Host 'Backend Server' -ForegroundColor Green; Write-Host '';"
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptPath\backend'; $backendInfo python -m uvicorn app.main:socket_app --host $backendHost --port 8000 --reload"

Start-Sleep -Seconds 3

# --- Start frontend ---
Write-Host "Starting frontend server..." -ForegroundColor Yellow

if ($Nginx) {
    # Nginx mode: frontend on localhost only
    $frontendInfo = "Write-Host 'Frontend Server (nginx mode)' -ForegroundColor Green; Write-Host 'Internal: http://localhost:3000' -ForegroundColor Yellow; Write-Host 'Public access via nginx on port 80' -ForegroundColor Cyan; Write-Host '';"
    $frontendCmd = "npm run dev"
} elseif ($Network) {
    $frontendInfo = "Write-Host 'Frontend Server - Network Mode' -ForegroundColor Green; Write-Host 'Starting with --host flag for network access...' -ForegroundColor Yellow; Write-Host '';"
    $frontendCmd = "npm run dev -- --host"
} else {
    $frontendInfo = "Write-Host 'Frontend Server' -ForegroundColor Green; Write-Host '';"
    $frontendCmd = "npm run dev"
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptPath\frontend'; $frontendInfo $frontendCmd"

Start-Sleep -Seconds 5

# --- Start nginx (if applicable) ---
if ($Nginx) {
    $nginxProcess = Get-Process nginx -ErrorAction SilentlyContinue
    if ($nginxProcess) {
        Write-Host "Stopping existing nginx process..." -ForegroundColor Yellow
        Stop-Process -Name nginx -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }

    Write-Host "Starting nginx reverse proxy on port 80..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\nginx; Write-Host 'nginx Reverse Proxy' -ForegroundColor Green; Write-Host 'Serving on port 80 (HTTP)' -ForegroundColor Yellow; Write-Host ''; .\nginx.exe"
    Start-Sleep -Seconds 2
}

# --- Summary ---
Write-Host ""
Write-Host "Application starting!" -ForegroundColor Green
Write-Host ""

if ($Nginx) {
    Write-Host "Local Access:" -ForegroundColor Cyan
    Write-Host "  Web App:  http://localhost" -ForegroundColor White
    Write-Host "  API Docs: http://localhost/docs" -ForegroundColor White
    Write-Host ""

    if ($networkIP) {
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
} else {
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
}

if (-not $Nginx) {
    Write-Host "Waiting for servers to initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
}

$browserUrl = if ($Nginx) { "http://localhost" } else { "http://localhost:3000" }
Write-Host "Opening browser..." -ForegroundColor Green
Start-Process $browserUrl

Write-Host ""
if ($Nginx) {
    Write-Host "To stop: close the PowerShell windows (backend, frontend) and run:" -ForegroundColor Yellow
    Write-Host "  Stop-Process -Name nginx -Force" -ForegroundColor White
} else {
    Write-Host "Press Ctrl+C in each terminal window to stop the servers" -ForegroundColor Yellow
}
