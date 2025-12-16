# Configure Windows Firewall for EEG Annotation Platform
# Run this script as Administrator

Write-Host "Configuring Windows Firewall for EEG Annotation Platform..." -ForegroundColor Green

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    pause
    exit 1
}

# Remove existing rules if they exist
Write-Host "Removing existing firewall rules (if any)..." -ForegroundColor Yellow
Remove-NetFirewallRule -DisplayName "EEG Platform Backend" -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName "EEG Platform Frontend" -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName "EEG Platform Port 80" -ErrorAction SilentlyContinue

# Create new firewall rules
Write-Host "Creating firewall rule for Backend (port 8000)..." -ForegroundColor Cyan
New-NetFirewallRule -DisplayName "EEG Platform Backend" `
    -Direction Inbound `
    -LocalPort 8000 `
    -Protocol TCP `
    -Action Allow `
    -Profile Domain,Private `
    -Description "Allows inbound connections to EEG Annotation Platform backend API"

Write-Host "Creating firewall rule for Frontend (port 3000)..." -ForegroundColor Cyan
New-NetFirewallRule -DisplayName "EEG Platform Frontend" `
    -Direction Inbound `
    -LocalPort 3000 `
    -Protocol TCP `
    -Action Allow `
    -Profile Domain,Private `
    -Description "Allows inbound connections to EEG Annotation Platform frontend"

Write-Host "Creating firewall rule for Port 80 (HTTP - Enterprise Friendly)..." -ForegroundColor Cyan
New-NetFirewallRule -DisplayName "EEG Platform Port 80" `
    -Direction Inbound `
    -LocalPort 80 `
    -Protocol TCP `
    -Action Allow `
    -Profile Domain,Private,Public `
    -Description "Allows HTTP access to EEG Annotation Platform on standard port 80 (firewall friendly)"

# Verify rules were created
Write-Host "`nVerifying firewall rules:" -ForegroundColor Green
Get-NetFirewallRule -DisplayName "EEG Platform*" | Select-Object DisplayName, Enabled, Direction, Action | Format-Table

Write-Host "`nFirewall configuration complete!" -ForegroundColor Green
Write-Host "Backend (port 8000) and Frontend (port 3000) are now accessible on the network." -ForegroundColor Green

# Display network information
Write-Host "`nYour network IP addresses:" -ForegroundColor Cyan
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object IPAddress, InterfaceAlias | Format-Table

Write-Host "Users on your network can access the platform at:" -ForegroundColor Yellow
$wifiIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -eq 'Wi-Fi' }).IPAddress
if ($wifiIP) {
    Write-Host "  Frontend: http://${wifiIP}:3000" -ForegroundColor Green
    Write-Host "  Backend:  http://${wifiIP}:8000" -ForegroundColor Green
}

Write-Host "`nPress any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
