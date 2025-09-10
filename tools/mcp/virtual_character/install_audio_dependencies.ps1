# PowerShell script to install audio routing dependencies
# Run as Administrator for best results

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Audio Routing Dependency Installer" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Host "WARNING: Not running as Administrator. Some installations may fail." -ForegroundColor Yellow
    Write-Host "Restart PowerShell as Administrator for best results." -ForegroundColor Yellow
    Write-Host ""
}

# Function to check if a command exists
function Test-CommandExists {
    param($Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

# Function to download file
function Download-File {
    param($Url, $Output)
    Write-Host "Downloading from $Url..." -ForegroundColor Gray
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Output -UseBasicParsing
        return $true
    } catch {
        Write-Host "Download failed: $_" -ForegroundColor Red
        return $false
    }
}

Write-Host "STEP 1: Checking Chocolatey Package Manager" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green

if (Test-CommandExists choco) {
    Write-Host "✓ Chocolatey is installed" -ForegroundColor Green
} else {
    Write-Host "✗ Chocolatey not found. Installing..." -ForegroundColor Yellow

    if ($isAdmin) {
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    } else {
        Write-Host "Cannot install Chocolatey without admin rights" -ForegroundColor Red
        Write-Host "Please run as Administrator or install manually from https://chocolatey.org" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "STEP 2: Installing Core Audio Tools" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green

# FFmpeg
Write-Host "Checking FFmpeg..." -ForegroundColor Gray
if (Test-CommandExists ffmpeg) {
    Write-Host "✓ FFmpeg is installed" -ForegroundColor Green
} else {
    Write-Host "Installing FFmpeg..." -ForegroundColor Yellow
    if (Test-CommandExists choco) {
        choco install ffmpeg -y
    } else {
        Write-Host "Please install FFmpeg manually from https://ffmpeg.org/download.html" -ForegroundColor Yellow
    }
}

# VLC
Write-Host "Checking VLC..." -ForegroundColor Gray
$vlcPaths = @(
    "${env:ProgramFiles}\VideoLAN\VLC\vlc.exe",
    "${env:ProgramFiles(x86)}\VideoLAN\VLC\vlc.exe"
)
$vlcFound = $false
foreach ($path in $vlcPaths) {
    if (Test-Path $path) {
        $vlcFound = $true
        Write-Host "✓ VLC is installed at: $path" -ForegroundColor Green

        # Add to PATH if not already there
        $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $vlcDir = Split-Path $path
        if ($currentPath -notlike "*$vlcDir*") {
            Write-Host "Adding VLC to PATH..." -ForegroundColor Yellow
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;$vlcDir", "User")
        }
        break
    }
}

if (-not $vlcFound) {
    Write-Host "Installing VLC..." -ForegroundColor Yellow
    if (Test-CommandExists choco) {
        choco install vlc -y
    } else {
        Write-Host "Please install VLC manually from https://www.videolan.org/vlc/" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "STEP 3: Installing Python Audio Packages" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green

# Check Python
Write-Host "Checking Python..." -ForegroundColor Gray
if (Test-CommandExists python) {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python is installed: $pythonVersion" -ForegroundColor Green

    # Install Python packages
    $packages = @(
        "pygame",
        "simpleaudio",
        "pyaudio",
        "sounddevice",
        "pycaw",
        "requests",
        "aiohttp"
    )

    Write-Host "Installing Python packages..." -ForegroundColor Yellow
    foreach ($package in $packages) {
        Write-Host "  Installing $package..." -ForegroundColor Gray
        python -m pip install --user $package 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ $package installed" -ForegroundColor Green
        } else {
            Write-Host "  ✗ $package failed to install" -ForegroundColor Red
        }
    }
} else {
    Write-Host "✗ Python not found. Please install Python from https://python.org" -ForegroundColor Red
}

Write-Host ""
Write-Host "STEP 4: Checking VoiceMeeter" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green

$voicemeeterPaths = @(
    "${env:ProgramFiles(x86)}\VB\Voicemeeter",
    "${env:ProgramFiles}\VB\Voicemeeter",
    "${env:ProgramFiles(x86)}\VB\VoicemeeterBanana",
    "${env:ProgramFiles}\VB\VoicemeeterBanana"
)

$voicemeeterFound = $false
foreach ($path in $voicemeeterPaths) {
    if (Test-Path $path) {
        $voicemeeterFound = $true
        Write-Host "✓ VoiceMeeter found at: $path" -ForegroundColor Green
        break
    }
}

if (-not $voicemeeterFound) {
    Write-Host "✗ VoiceMeeter not found" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please install VoiceMeeter manually:" -ForegroundColor Yellow
    Write-Host "1. Go to https://vb-audio.com/Voicemeeter/" -ForegroundColor Cyan
    Write-Host "2. Download VoiceMeeter or VoiceMeeter Banana" -ForegroundColor Cyan
    Write-Host "3. Install and restart your computer" -ForegroundColor Cyan
} else {
    # Check if VoiceMeeter is running
    $process = Get-Process -Name "voicemeeter*" -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "✓ VoiceMeeter is running" -ForegroundColor Green
    } else {
        Write-Host "! VoiceMeeter is installed but not running" -ForegroundColor Yellow
        Write-Host "  Please start VoiceMeeter before testing" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "STEP 5: System Configuration" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green

# Check PowerShell execution policy
$executionPolicy = Get-ExecutionPolicy
Write-Host "PowerShell Execution Policy: $executionPolicy" -ForegroundColor Gray
if ($executionPolicy -eq "Restricted") {
    Write-Host "Setting execution policy to RemoteSigned..." -ForegroundColor Yellow
    Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
}

# Check .NET Framework
Write-Host "Checking .NET Framework..." -ForegroundColor Gray
$dotNetVersion = Get-ItemProperty "HKLM:SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full\" -Name Release -ErrorAction SilentlyContinue
if ($dotNetVersion) {
    $release = $dotNetVersion.Release
    $version = switch ($release) {
        { $_ -ge 533320 } { "4.8.1 or later" }
        { $_ -ge 528040 } { "4.8" }
        { $_ -ge 461808 } { "4.7.2" }
        { $_ -ge 461308 } { "4.7.1" }
        { $_ -ge 460798 } { "4.7" }
        default { "4.6 or earlier" }
    }
    Write-Host "✓ .NET Framework version: $version" -ForegroundColor Green
} else {
    Write-Host "✗ .NET Framework 4.x not detected" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "STEP 6: Creating Test Directory" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green

$testDir = "$env:USERPROFILE\VoiceMeeterAudioTests"
if (-not (Test-Path $testDir)) {
    New-Item -ItemType Directory -Path $testDir -Force | Out-Null
    Write-Host "✓ Created test directory: $testDir" -ForegroundColor Green
} else {
    Write-Host "✓ Test directory exists: $testDir" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Installation Summary" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Summary
$summary = @{
    "Chocolatey" = Test-CommandExists choco
    "FFmpeg" = Test-CommandExists ffmpeg
    "VLC" = $vlcFound
    "Python" = Test-CommandExists python
    "VoiceMeeter" = $voicemeeterFound
}

foreach ($tool in $summary.Keys) {
    $status = if ($summary[$tool]) { "✓ Installed" } else { "✗ Not Installed" }
    $color = if ($summary[$tool]) { "Green" } else { "Red" }
    Write-Host "$tool : $status" -ForegroundColor $color
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. If VoiceMeeter is not installed, install it and restart" -ForegroundColor Cyan
Write-Host "2. Start VoiceMeeter" -ForegroundColor Cyan
Write-Host "3. Configure Windows audio (set VoiceMeeter Input as default)" -ForegroundColor Cyan
Write-Host "4. Run the test script: python test_audio_routing_comprehensive.py" -ForegroundColor Cyan

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
