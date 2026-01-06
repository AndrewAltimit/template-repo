# GPU Orchestrator - Windows Setup Guide

Quick setup guide specifically for Windows GPU machines.

## Prerequisites

1. **Docker Desktop for Windows**
   - Download: https://www.docker.com/products/docker-desktop
   - Must have WSL2 backend enabled
   - Ensure "Use WSL 2 based engine" is checked in Docker Desktop settings

2. **NVIDIA GPU Drivers**
   - Download latest drivers: https://www.nvidia.com/drivers
   - Install and restart

3. **NVIDIA Container Toolkit** (for Docker GPU support)
   - Usually included with Docker Desktop
   - Verify with: `docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`

4. **Python 3.8+**
   - Download: https://www.python.org/downloads/
   - During installation, check "Add Python to PATH"

5. **Git for Windows**
   - Download: https://git-scm.com/download/win
   - For cloning/pulling repository

## Quick Start (Windows)

### Step 1: Open PowerShell or Command Prompt

```cmd
# Open as Administrator (recommended)
# Right-click Start → Windows Terminal (Admin)
```

### Step 2: Clone Repository (if not already done)

```cmd
cd C:\
git clone https://github.com/AndrewAltimit/template-repo
cd template-repo
```

### Step 3: Checkout Branch and Navigate

```cmd
git checkout sleeper-dashboard
git pull origin sleeper-dashboard
cd packages\sleeper_agents\gpu_orchestrator
```

### Step 4: Configure API Key

```cmd
# Copy template
copy .env.example .env

# Edit .env with Notepad
notepad .env

# Change this line:
# API_KEY=your-secure-api-key-here
# To something secure:
# API_KEY=my-secure-key-12345
```

### Step 5: Build Docker Image (first time only)

```cmd
# Go back to sleeper_agents directory
cd ..

# Build GPU image
docker build -t sleeper-agents:gpu -f docker\Dockerfile.gpu .

# This will take 5-10 minutes
# Expected: "Successfully tagged sleeper-agents:gpu"
```

### Step 6: Start API

```cmd
# Go back to orchestrator directory
cd gpu_orchestrator

# Run startup script
start_orchestrator.bat
```

**Expected Output**:
```
=========================================
GPU Orchestrator API Startup
=========================================

[1/5] Checking prerequisites...
GPU detected:
  NVIDIA GeForce RTX 3090, 24576 MB
[2/5] Setting up environment...
[3/5] Installing dependencies...
[4/5] Checking Docker image...
[5/5] Starting GPU Orchestrator API...

API will be available at:
  - Local: http://localhost:8000
  - Network: http://192.168.0.152:8000
  - Docs: http://localhost:8000/docs

Press Ctrl+C to stop

INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Step 7: Test API (in new terminal)

Open a **new Command Prompt** or **PowerShell**:

```cmd
# Health check
curl http://localhost:8000/health

# System status (replace API key with yours from .env)
curl -H "X-API-Key: my-secure-key-12345" http://localhost:8000/api/system/status
```

Or open in browser:
- http://localhost:8000/health
- http://localhost:8000/docs (interactive API documentation)

## Troubleshooting (Windows-Specific)

### Issue: "Python not found"

**Solution**:
1. Install Python from https://www.python.org/downloads/
2. During installation, check "Add Python to PATH"
3. Restart terminal
4. Verify: `python --version`

### Issue: "Docker not found" or "Docker daemon not running"

**Solution**:
1. Install Docker Desktop: https://www.docker.com/products/docker-desktop
2. Start Docker Desktop (it must be running)
3. Wait for "Docker Desktop is running" in system tray
4. Verify: `docker info`

### Issue: "nvidia-smi not found"

**Solution**:
1. Install NVIDIA drivers: https://www.nvidia.com/drivers
2. Restart computer
3. Verify: `nvidia-smi`

### Issue: "Access denied" when running scripts

**Solution**:
```cmd
# Run PowerShell or Command Prompt as Administrator
# Right-click Start → Windows Terminal (Admin)
```

### Issue: "docker build" fails with permission errors

**Solution**:
1. Make sure Docker Desktop is running
2. Run terminal as Administrator
3. Check Docker Desktop → Settings → Resources → WSL Integration
4. Enable integration for your WSL distro

### Issue: Port 8000 already in use

**Solution**:
```cmd
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with actual process ID)
taskkill /PID <pid> /F

# Or change API_PORT in .env:
# API_PORT=8001
```

### Issue: "ModuleNotFoundError" when starting API

**Solution**:
```cmd
# Make sure virtual environment is activated
venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Firewall blocking connections from other machines

**Solution**:
1. Open Windows Defender Firewall
2. Advanced Settings → Inbound Rules
3. New Rule → Port → TCP → 8000
4. Allow the connection
5. Name it "GPU Orchestrator API"

## Windows-Specific Notes

### Virtual Environment Activation

Windows uses different activation command:
```cmd
# Command Prompt
venv\Scripts\activate.bat

# PowerShell
venv\Scripts\Activate.ps1
```

### Path Separators

Windows uses backslashes:
```cmd
# Windows
cd packages\sleeper_agents\gpu_orchestrator

# Linux/Mac
cd packages/sleeper_agents/gpu_orchestrator
```

### Line Endings

If you get errors about line endings:
```cmd
# Configure git to handle line endings
git config --global core.autocrlf true
```

### Docker Volume Paths

Windows Docker uses different volume mounting:
- Named volumes work the same: `sleeper-models:/models`
- Host paths need Windows format: `C:\path\to\folder:/app`

## Running in Background

To run the API in background (not blocking terminal):

### Option 1: Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Action: Start a Program
4. Program: `C:\path\to\template-repo\packages\sleeper_agents\gpu_orchestrator\start_orchestrator.bat`
5. Set to run at startup

### Option 2: NSSM (Non-Sucking Service Manager)

```cmd
# Download NSSM: https://nssm.cc/download
# Install as Windows service
nssm install GPUOrchestrator "C:\path\to\venv\Scripts\python.exe" "-m" "uvicorn" "api.main:app" "--host" "0.0.0.0" "--port" "8000"
nssm start GPUOrchestrator
```

### Option 3: Start Minimized

```cmd
# Create a shortcut to start_orchestrator.bat
# Right-click → Properties → Run: Minimized
```

## Testing Commands (Windows)

All testing commands from TESTING.md work on Windows, but use these tools:

### Using curl (if installed)
```cmd
curl http://localhost:8000/health
```

### Using PowerShell (if curl not available)
```powershell
Invoke-WebRequest -Uri http://localhost:8000/health
```

### Using browser
- http://localhost:8000/docs - Interactive API testing
- http://localhost:8000/health - Health check

## Next Steps

After API is running:
1. Note your machine's IP address (shown in startup message)
2. Test from another machine: `http://YOUR_IP:8000/health`
3. Configure dashboard to connect to: `http://YOUR_IP:8000`
4. Proceed to Dashboard Build Category

## Stopping the API

```cmd
# In the terminal running the API, press:
Ctrl+C

# If running as service:
nssm stop GPUOrchestrator
```

## Cleanup

```cmd
# Remove virtual environment
rmdir /s venv

# Remove database
del orchestrator.db

# Remove Docker containers
docker container prune -f
```

---

**Windows setup complete!** The API should now be running and accessible from your network.
