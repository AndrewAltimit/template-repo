#!/usr/bin/env pwsh
# DEPRECATED: This location has moved
# Redirecting to the new unified virtual-character launcher

Write-Host "[NOTICE] This script location is deprecated." -ForegroundColor Yellow
Write-Host "[NOTICE] Redirecting to: automation/launchers/windows/virtual-character/" -ForegroundColor Yellow
Write-Host ""

& "$PSScriptRoot\..\virtual-character\start_server_windows.ps1" @args
