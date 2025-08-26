#!/usr/bin/env pwsh
# Convenience script that calls the main launcher
# The actual script is in automation/launchers/windows/vrchat/

Write-Host "Redirecting to main launcher script..." -ForegroundColor Yellow
& "$PSScriptRoot\..\..\..\..\automation\launchers\windows\vrchat\start_server_windows.ps1" @args
