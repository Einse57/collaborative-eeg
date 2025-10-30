# EEG/MEG Annotation Platform - Startup Script
# This script starts both the backend and frontend servers

Write-Host "🧠 Starting EEG/MEG Annotation Platform..." -ForegroundColor Cyan

# Detect network IP address
Write-Host ""
Write-Host "Detecting network configuration..." -ForegroundColor Yellow
$networkIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
    $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*"
} | Select-Object -First 1).IPAddress

if ($networkIP) {
    Write-Host "✓ Network IP detected: $networkIP" -ForegroundColor Green
    
    # Check if .env exists and is configured correctly
    $envPath = "$PWD\frontend\.env"
    $envContent = "VITE_API_URL=http://${networkIP}:8000"
    
    if (Test-Path $envPath) {
        $currentContent = Get-Content $envPath -Raw
        if ($currentContent -notmatch "VITE_API_URL=http://${networkIP}:8000") {
            Write-Host "⚙️  Updating frontend/.env with network IP..." -ForegroundColor Yellow
            Set-Content -Path $envPath -Value "# Backend API URL - Auto-configured`n$envContent`n"
            Write-Host "✓ Updated .env file" -ForegroundColor Green
        }
    } else {
        Write-Host "⚙️  Creating frontend/.env with network IP..." -ForegroundColor Yellow
        Set-Content -Path $envPath -Value "# Backend API URL - Auto-configured`n$envContent`n"
        Write-Host "✓ Created .env file" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "📡 Access URLs:" -ForegroundColor Cyan
    Write-Host "   Local:  http://localhost:3000" -ForegroundColor White
    Write-Host "   Network: http://${networkIP}:3000" -ForegroundColor Green
    Write-Host "   Backend: http://${networkIP}:8000" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "⚠️  Could not detect network IP. Using localhost only." -ForegroundColor Yellow
    $envPath = "$PWD\frontend\.env"
    Set-Content -Path $envPath -Value "# Backend API URL`nVITE_API_URL=http://localhost:8000`n"
}

Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found. Please install Python 3.9+" -ForegroundColor Red
    exit 1
}

# Check if Node.js is installed
try {
    $nodeVersion = node --version 2>&1
    Write-Host "✓ Node.js found: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Node.js not found. Please install Node.js 18+" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting backend server..." -ForegroundColor Yellow

# Start backend in a new PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\backend'; if (Test-Path '.\venv\Scripts\Activate.ps1') { .\venv\Scripts\Activate.ps1 } else { Write-Host 'Virtual environment not found. Run: python -m venv venv' -ForegroundColor Red }; uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload"

Start-Sleep -Seconds 3

Write-Host "Starting frontend server..." -ForegroundColor Yellow

# Start frontend in a new PowerShell window  
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\frontend'; npm run dev"

Write-Host ""
Write-Host "🎉 Application starting!" -ForegroundColor Green
Write-Host ""
Write-Host "📡 Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "📡 API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "🌐 Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C in each terminal window to stop the servers" -ForegroundColor Yellow
