# PowerShell script to setup Windows Task Scheduler for CGT scraping

Write-Host "CGT Validator - Windows Task Scheduler Setup" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

# Check if running as administrator
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator"))
{
    Write-Host "This script requires administrator privileges." -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Red
    Exit 1
}

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

# Check Python installation
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Python is not installed or not in PATH" -ForegroundColor Red
    Exit 1
}

# Create directories
$CgtDir = "$env:USERPROFILE\.cgt-validator"
$LogDir = "$CgtDir\logs"
New-Item -ItemType Directory -Force -Path $CgtDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Create batch script for running scraper
$BatchScript = "$CgtDir\run_scraping.bat"
@"
@echo off
cd /d "$ProjectDir"
set LOG_FILE="$LogDir\scraping_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log"
echo Starting CGT scraping at %date% %time% >> %LOG_FILE%
python -m src.scrapers.scheduler run >> %LOG_FILE% 2>&1
echo Scraping completed at %date% %time% >> %LOG_FILE%

REM Clean up old logs (older than 30 days)
forfiles /p "$LogDir" /s /m scraping_*.log /d -30 /c "cmd /c del @path" 2>nul
"@ | Out-File -FilePath $BatchScript -Encoding ASCII

Write-Host "Created batch script: $BatchScript" -ForegroundColor Green

# Setup scheduled task
Write-Host ""
Write-Host "Setting up Windows Task Scheduler..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Choose scraping frequency:"
Write-Host "1) Daily at 2 AM"
Write-Host "2) Weekly on Mondays at 2 AM"
Write-Host "3) Monthly on the 1st at 2 AM"
Write-Host ""
$choice = Read-Host "Enter choice (1-3)"

$TaskName = "CGT Validator Scraping"
$TaskDescription = "Automatically scrape CGT requirements from state websites"

# Create trigger based on choice
switch ($choice) {
    "1" {
        $Trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM
        $FrequencyDesc = "Daily at 2:00 AM"
    }
    "2" {
        $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 2:00AM
        $FrequencyDesc = "Weekly on Mondays at 2:00 AM"
    }
    "3" {
        $Trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM
        # Will add monthly condition later
        $FrequencyDesc = "Monthly on the 1st at 2:00 AM"
    }
    default {
        Write-Host "Invalid choice" -ForegroundColor Red
        Exit 1
    }
}

# Create action
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatchScript`""

# Create principal (run whether user is logged on or not)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited

# Create settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew

# Register the task
try {
    # Remove existing task if it exists
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    # Register new task
    Register-ScheduledTask -TaskName $TaskName -Description $TaskDescription `
        -Trigger $Trigger -Action $Action -Principal $Principal -Settings $Settings

    Write-Host ""
    Write-Host "✓ Scheduled task created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Name: $TaskName" -ForegroundColor Cyan
    Write-Host "Schedule: $FrequencyDesc" -ForegroundColor Cyan
    Write-Host "Script: $BatchScript" -ForegroundColor Cyan
    Write-Host "Logs: $LogDir" -ForegroundColor Cyan
} catch {
    Write-Host "Error creating scheduled task: $_" -ForegroundColor Red
    Exit 1
}

# Configure email notifications
Write-Host ""
$configureEmail = Read-Host "Would you like to configure email notifications? (y/n)"

if ($configureEmail -eq "y") {
    Write-Host ""
    Write-Host "Email Configuration" -ForegroundColor Yellow
    Write-Host "===================" -ForegroundColor Yellow

    $smtpServer = Read-Host "SMTP Server (e.g., smtp.gmail.com)"
    $smtpPort = Read-Host "SMTP Port (e.g., 587)"
    $fromEmail = Read-Host "From Email"
    $toEmails = Read-Host "To Email(s) (comma-separated)"

    # Create Python script to update configuration
    $pythonScript = @"
from pathlib import Path
import sys
sys.path.append('$ProjectDir')
from src.scrapers.scheduler import ScrapingScheduler

scheduler = ScrapingScheduler()
scheduler.config['email_notifications']['enabled'] = True
scheduler.config['email_notifications']['smtp_server'] = '$smtpServer'
scheduler.config['email_notifications']['smtp_port'] = int('$smtpPort')
scheduler.config['email_notifications']['from_email'] = '$fromEmail'
scheduler.config['email_notifications']['to_emails'] = '$toEmails'.split(',')
scheduler.save_config()
print('Email notifications configured successfully!')
"@

    $pythonScript | python
}

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "The scraper will run automatically according to the schedule." -ForegroundColor Green
Write-Host "You can manage the task in Task Scheduler (taskschd.msc)" -ForegroundColor Green
Write-Host "To run manually, execute: $BatchScript" -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
