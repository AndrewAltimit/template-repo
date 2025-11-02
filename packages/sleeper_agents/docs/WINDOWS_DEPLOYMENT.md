# Windows Deployment Guide

## Overview

This guide covers deploying the sleeper detection system on Windows platforms, including native Windows, WSL2, and Docker Desktop configurations.

## Deployment Options

### Option 1: Docker Desktop (Recommended)

Docker Desktop provides the most consistent experience on Windows.

#### Installation

1. **Install Docker Desktop**
   ```powershell
   # Download from Docker website
   # https://www.docker.com/products/docker-desktop/

   # Or use Chocolatey
   choco install docker-desktop
   ```

2. **Configure Docker Desktop**
   - Enable WSL2 backend (recommended)
   - Allocate sufficient resources (Settings → Resources)
   - Minimum: 4GB RAM, 2 CPUs
   - Recommended: 8GB RAM, 4 CPUs

3. **Clone Repository**
   ```powershell
   git clone https://github.com/AndrewAltimit/template-repo.git
   cd template-repo
   ```

4. **Start Services**
   ```powershell
   docker-compose up -d sleeper-eval-cpu
   ```

#### Windows User ID Limitations

⚠️ **Important Note**: The Windows PowerShell script `automation/sleeper-agents/windows/run_evaluation.ps1` contains hardcoded user and group IDs:

```powershell
$env:USER_ID = "1000"
$env:GROUP_ID = "1000"
```

This differs from the Linux environment where these values are determined dynamically. If your Windows user/group ID does not match 1000, you may encounter file permission errors when writing to mounted volumes.

**Workarounds:**
1. **Manual Override**: Set the correct IDs before running scripts:
   ```powershell
   $env:USER_ID = "your_id"
   $env:GROUP_ID = "your_group_id"
   docker-compose up -d sleeper-eval-cpu
   ```

2. **Use WSL2**: WSL2 provides better Unix-style permission handling
3. **Run as Administrator**: May bypass some permission issues but is not recommended for security reasons

Note: Mapping Windows SIDs to Linux-style UIDs inside containers is non-trivial. The hardcoded values work for most Docker Desktop installations but may need adjustment in enterprise environments.

### Option 2: WSL2 (Windows Subsystem for Linux)

WSL2 provides near-native Linux performance on Windows.

#### Setup WSL2

```powershell
# Enable WSL2
wsl --install

# Set WSL2 as default
wsl --set-default-version 2

# Install Ubuntu
wsl --install -d Ubuntu-22.04

# Enter WSL2 environment
wsl
```

#### Install in WSL2

```bash
# Inside WSL2
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install python3.11 python3.11-pip python3.11-venv

# Clone repository
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r config/python/requirements-sleeper-agents.txt
```

### Option 3: Native Windows Python

For development without containers.

#### Prerequisites

```powershell
# Install Python 3.11
# Download from python.org or use Chocolatey
choco install python311

# Install Git
choco install git

# Install Visual Studio Build Tools (for some packages)
choco install visualstudio2022-workload-vctools
```

#### Installation

```powershell
# Clone repository
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install PyTorch (CPU version for Windows)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install other dependencies
pip install -r config/python/requirements-sleeper-agents.txt
```

## GPU Support on Windows

### CUDA Setup

```powershell
# Check NVIDIA GPU
nvidia-smi

# Install CUDA Toolkit 11.8
# Download from: https://developer.nvidia.com/cuda-11-8-0-download-archive

# Install cuDNN
# Download from: https://developer.nvidia.com/cudnn

# Install PyTorch with CUDA
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### Docker GPU Support

```yaml
# docker-compose.override.yml for Windows GPU
services:
  sleeper-eval-gpu:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

## Windows-Specific Configuration

### Path Configuration

```powershell
# Windows paths in .env file
TRANSFORMERS_CACHE=C:\Users\%USERNAME%\AppData\Local\huggingface\models
EVAL_RESULTS_DIR=C:\sleeper_agents\results
EVAL_DB_PATH=C:\sleeper_agents\evaluation.db
```

### PowerShell Scripts

```powershell
# scripts/windows/run-detection.ps1
param(
    [string]$Model = "pythia-70m",
    [string]$Text = "Test input",
    [switch]$UseDocker
)

if ($UseDocker) {
    docker run --rm `
        -v ${PWD}:/app `
        sleeper-eval-cpu `
        python -m packages.sleeper_agents.cli detect `
        --model $Model --text $Text
} else {
    & python -m packages.sleeper_agents.cli detect `
        --model $Model --text $Text
}
```

## Service Deployment

### Windows Service Setup

```powershell
# Install as Windows Service using NSSM
nssm install SleeperDetectionAPI `
    "C:\Python311\python.exe" `
    "C:\repos\template-repo\packages\sleeper_agents\api\main.py"

# Configure service
nssm set SleeperDetectionAPI AppDirectory C:\repos\template-repo
nssm set SleeperDetectionAPI AppEnvironmentExtra PYTHONPATH=C:\repos\template-repo

# Start service
nssm start SleeperDetectionAPI
```

### IIS Integration

```xml
<!-- web.config for IIS -->
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="PythonHandler"
           path="*"
           verb="*"
           modules="FastCgiModule"
           scriptProcessor="C:\Python311\python.exe|C:\repos\template-repo\packages\sleeper_agents\api\main.py"
           resourceType="Unspecified" />
    </handlers>
  </system.webServer>
</configuration>
```

## Performance Optimization

### Windows-Specific Optimizations

```python
# Windows memory management
import sys
if sys.platform == "win32":
    import psutil

    # Set process priority
    process = psutil.Process()
    process.nice(psutil.HIGH_PRIORITY_CLASS)

    # Configure memory limits
    process.memory_info()

    # Use Windows-optimized settings
    config = DetectionConfig(
        model_name="pythia-70m",
        device="cpu",
        num_threads=psutil.cpu_count(logical=False),
        use_memory_mapping=True
    )
```

### Disk I/O Optimization

```powershell
# Configure Windows Defender exclusions
Add-MpPreference -ExclusionPath "C:\Users\$env:USERNAME\AppData\Local\huggingface"
Add-MpPreference -ExclusionPath "C:\sleeper_agents"

# Disable indexing on model cache
attrib +I "C:\Users\$env:USERNAME\AppData\Local\huggingface"
```

## Troubleshooting Windows Issues

### Common Problems and Solutions

#### Long Path Issues

```powershell
# Enable long path support
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
    -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

#### Permission Errors

```powershell
# Run as Administrator or fix permissions
icacls "C:\sleeper_agents" /grant "${env:USERNAME}:(OI)(CI)F" /T
```

#### DLL Loading Errors

```powershell
# Install Visual C++ Redistributables
choco install vcredist-all

# Or download from Microsoft
# https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist
```

#### PyTorch CUDA Issues

```python
# Debug CUDA availability
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda}")
print(f"cuDNN version: {torch.backends.cudnn.version()}")

# Force CPU if CUDA issues
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
```

## Network Deployment

### Firewall Configuration

```powershell
# Allow API port
New-NetFirewallRule -DisplayName "Sleeper Detection API" `
    -Direction Inbound -LocalPort 8021 -Protocol TCP -Action Allow
```

### Remote Access Setup

```powershell
# Configure for remote access
# Update API configuration
$config = @"
API_HOST=0.0.0.0
API_PORT=8021
CORS_ORIGINS=["http://localhost:3000", "https://your-domain.com"]
"@
$config | Out-File -FilePath .env -Encoding UTF8
```

## Monitoring on Windows

### Performance Monitoring

```powershell
# Monitor resource usage
Get-Process python* | Select-Object ProcessName, CPU, WS

# Monitor with Performance Counter
Get-Counter "\Process(python*)\% Processor Time"
Get-Counter "\Process(python*)\Working Set"
```

### Logging Configuration

```python
# Windows-specific logging
import logging
import logging.handlers

# Windows Event Log handler
if sys.platform == "win32":
    import win32evtlogutil
    handler = logging.handlers.NTEventLogHandler("Sleeper Detection")
    handler.setLevel(logging.WARNING)
    logger.addHandler(handler)

# File logging with Windows paths
file_handler = logging.FileHandler(
    r"C:\sleeper_agents\logs\detection.log"
)
```

## Backup and Recovery

### Automated Backup Script

```powershell
# backup-sleeper-agents.ps1
$date = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = "C:\Backups\sleeper_agents_$date"

# Backup models and results
robocopy "C:\Users\$env:USERNAME\AppData\Local\huggingface" `
    "$backupPath\models" /E /MT:8

robocopy "C:\sleeper_agents\results" `
    "$backupPath\results" /E /MT:8

# Compress backup
Compress-Archive -Path $backupPath `
    -DestinationPath "$backupPath.zip"
```

## Best Practices for Windows

1. **Use Docker Desktop** when possible for consistency
2. **WSL2** provides better compatibility than native Windows
3. **Regular Updates**: Keep Windows, Docker, and Python updated
4. **Antivirus Exclusions**: Exclude model cache and work directories
5. **Path Management**: Use forward slashes or raw strings in Python
6. **Resource Monitoring**: Windows can have different memory behavior
7. **GPU Drivers**: Keep NVIDIA drivers updated for GPU support
