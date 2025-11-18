# EEG/MEG Annotation Platform - Startup Script
# This script starts both the backend and frontend servers

Write-Host "Starting EEG/MEG Annotation Platform..." -ForegroundColor Cyan

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
Write-Host "Starting backend server..." -ForegroundColor Yellow

# Start backend in a new PowerShell window
# Use venv's python directly to ensure packages are available
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\backend'; if (Test-Path '.\venv\Scripts\python.exe') { .\venv\Scripts\python.exe -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload } else { python -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload }"

Start-Sleep -Seconds 3

Write-Host "Starting frontend server..." -ForegroundColor Yellow

# Start frontend in a new PowerShell window  
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\frontend'; npm run dev"

Write-Host ""
Write-Host "Application starting!" -ForegroundColor Green
Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Waiting for servers to initialize..." -ForegroundColor Yellow

# Wait for backend to be ready (plugins loading, etc.)
Start-Sleep -Seconds 5

# Wait for frontend dev server to be ready
Start-Sleep -Seconds 3

Write-Host "Opening browser..." -ForegroundColor Green
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "Press Ctrl+C in each terminal window to stop the servers" -ForegroundColor Yellow
