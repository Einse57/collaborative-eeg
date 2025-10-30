# EEG/MEG Annotation Platform - Setup Script
# Run this script on first installation

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  EEG/MEG Annotation Platform - Setup" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found. Please install Python 3.9+" -ForegroundColor Red
    Write-Host "   Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Check Node.js
Write-Host "Checking Node.js installation..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host "✓ Node.js found: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Node.js not found. Please install Node.js 18+" -ForegroundColor Red
    Write-Host "   Download from: https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Setting up backend..." -ForegroundColor Cyan

# Create Python virtual environment
if (-not (Test-Path "backend\venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    Set-Location backend
    python -m venv venv
    Set-Location ..
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "✓ Virtual environment already exists" -ForegroundColor Green
}

# Install Python dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
Set-Location backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
deactivate
Set-Location ..
Write-Host "✓ Python dependencies installed" -ForegroundColor Green

Write-Host ""
Write-Host "Setting up frontend..." -ForegroundColor Cyan

# Install Node.js dependencies
Write-Host "Installing Node.js dependencies..." -ForegroundColor Yellow
Set-Location frontend
npm install
Set-Location ..
Write-Host "✓ Node.js dependencies installed" -ForegroundColor Green

Write-Host ""
Write-Host "Configuring network settings..." -ForegroundColor Cyan

# Detect network IP
$networkIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
    $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*"
} | Select-Object -First 1).IPAddress

if ($networkIP) {
    Write-Host "✓ Network IP detected: $networkIP" -ForegroundColor Green
    
    # Create .env file
    $envPath = "frontend\.env"
    $envContent = "# Backend API URL - Auto-configured`nVITE_API_URL=http://${networkIP}:8000`n"
    Set-Content -Path $envPath -Value $envContent
    Write-Host "✓ Created frontend/.env" -ForegroundColor Green
    
    # Create uploads directory
    if (-not (Test-Path "backend\uploads")) {
        New-Item -ItemType Directory -Path "backend\uploads" | Out-Null
        Write-Host "✓ Created uploads directory" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Green
    Write-Host "  Setup Complete!" -ForegroundColor Green
    Write-Host "===========================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Configure Windows Firewall (run as Administrator):" -ForegroundColor White
    Write-Host "   .\configure-firewall.ps1" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "2. Start the application:" -ForegroundColor White
    Write-Host "   .\start.ps1" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Access URLs:" -ForegroundColor Cyan
    Write-Host "   Local:   http://localhost:3000" -ForegroundColor White
    Write-Host "   Network: http://${networkIP}:3000" -ForegroundColor Green
    Write-Host "   Backend: http://${networkIP}:8000" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "⚠️  Could not detect network IP" -ForegroundColor Yellow
    Write-Host "   Using localhost configuration" -ForegroundColor Yellow
    
    $envPath = "frontend\.env"
    Set-Content -Path $envPath -Value "# Backend API URL`nVITE_API_URL=http://localhost:8000`n"
    
    Write-Host ""
    Write-Host "Setup complete! Run .\start.ps1 to start the application." -ForegroundColor Green
}

Write-Host ""
