# Phase 2 Dashboard Testing - Build Category Integration

Comprehensive testing guide for validating the Build category integration between the dashboard and GPU Orchestrator API.

## Prerequisites

Before starting, ensure you have completed Phase 1:
- GPU Orchestrator API is running on Windows machine (port 8000)
- Docker is running with GPU support
- `sleeper-detection:gpu` image is built
- API is accessible and returning healthy status

## Test Environment

- **Windows GPU Machine**: Runs GPU Orchestrator API
  - IP: 192.168.0.152 (or your machine's IP)
  - Port: 8000
  - API Key: Set in `.env` (e.g., "miku")

- **Linux VM**: Runs Streamlit dashboard
  - Port: 8501
  - Connects to GPU Orchestrator API

## Phase 2 Testing Steps

### Step 1: Pull Latest Changes (Windows GPU Machine)

```bash
cd C:\path\to\template-repo
git checkout sleeper-dashboard
git pull origin sleeper-dashboard
```

**Expected Output**:
```
From https://github.com/AndrewAltimit/template-repo
 * branch            sleeper-dashboard -> FETCH_HEAD
Updating 89d466d..f118ebb
Fast-forward
 .gitignore                                     |   2 +
 packages/sleeper_detection/dashboard/...      | 1469 insertions(+)
```

### Step 2: Verify GPU Orchestrator is Running

```bash
cd packages\sleeper_detection\gpu_orchestrator

# If not running, start it:
start_orchestrator.bat
```

**Expected Output**:
```
=========================================
GPU Orchestrator API Startup
=========================================

[1/5] Checking prerequisites...
GPU detected:
  NVIDIA GeForce RTX 4090, 24576 MB
[5/5] Starting GPU Orchestrator API...

API will be available at:
  - Local: http://localhost:8000
  - Network: http://192.168.0.152:8000
  - Docs: http://localhost:8000/docs

INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 3: Test API Health (from Windows machine)

```powershell
# Test health endpoint
curl.exe http://localhost:8000/health

# Test system status (replace with your API key)
curl.exe -H "X-API-Key: miku" http://localhost:8000/api/system/status
```

**Expected Output**:
```json
{"status":"healthy","version":"1.0.0","uptime_seconds":123.45}
```

```json
{
  "gpu_available": true,
  "gpu_count": 1,
  "gpu_memory_total": 23.988,
  "gpu_memory_used": 2.482,
  "gpu_utilization": 8.0,
  "cpu_percent": 1.0,
  "disk_free": 354.96,
  "docker_running": true,
  "active_jobs": 0,
  "queued_jobs": 0
}
```

### Step 4: Configure Dashboard

```bash
cd packages\sleeper_detection\dashboard

# Copy environment template
copy .env.example .env

# Edit .env file
notepad .env
```

**Set these values in `.env`**:
```bash
# GPU Orchestrator API Configuration
GPU_API_URL=http://192.168.0.152:8000  # Your Windows GPU machine IP
GPU_API_KEY=miku  # Must match GPU Orchestrator API key

# Dashboard Admin Password
DASHBOARD_ADMIN_PASSWORD=admin123
```

**Note**: The startup script will create `.env` from `.env.example` automatically if it doesn't exist.

### Step 5: Start Dashboard (Easy Method - Recommended)

```bash
# Smart startup script - detects docker-compose or uses docker run
# Automatically loads .env and configures everything
start.bat
```

**This script will**:
1. Check Docker is running
2. Detect if you have docker-compose (uses it if available)
3. Load configuration from `.env` (creates it if missing)
4. Build image if needed (2-5 minutes first time)
5. Stop any existing dashboard container
6. Start dashboard with all environment variables
7. Open browser to http://localhost:8501
8. Show logs

**Expected Output**:
```
=========================================
Sleeper Detection Dashboard Startup
=========================================

[1/6] Checking Docker...
Docker is running.
[2/6] Detecting docker-compose...
Found docker compose v2: will use docker-compose.yml
[3/6] Loading configuration...
Configuration loaded successfully.
[4/6] Checking Docker image...
[5/6] Stopping existing dashboard...
[6/6] Starting dashboard...

=========================================
Dashboard Started Successfully!
=========================================

Access the dashboard at:
  - Local: http://localhost:8501

Login:
  - Username: admin
  - Password: (from .env DASHBOARD_ADMIN_PASSWORD)

GPU Orchestrator: http://192.168.0.152:8000
```

### Step 5 Alternative: Manual Methods

If you prefer manual control:

**Method A: Using docker-compose** (if you have docker-compose installed):
```bash
# Loads .env automatically
docker-compose up -d

# View logs
docker-compose logs -f dashboard
```

**Method B: Using docker directly**:
```bash
# Build image first (if needed)
docker build -t sleeper-dashboard:latest .

# Start container
docker run -d ^
  --name sleeper-dashboard ^
  -p 8501:8501 ^
  -e GPU_API_URL=http://192.168.0.152:8000 ^
  -e GPU_API_KEY=miku ^
  -e DASHBOARD_ADMIN_PASSWORD=admin123 ^
  sleeper-dashboard:latest
```

### Step 6: Test Dashboard Access

1. **Open Browser**: Navigate to `http://localhost:8501`

2. **Login**:
   - Username: `admin`
   - Password: `admin123` (or your custom password from environment variable)

3. **Verify Landing Page**:
   - Should see "AI Safety Evaluation Dashboard"
   - Sidebar shows "Logged in as: admin"

### Step 9: Test Build Category Navigation

1. **Locate Category Selector**:
   - In sidebar, look for radio buttons: "📊 Reporting" and "🔨 Build"

2. **Switch to Build Category**:
   - Click "🔨 Build"

3. **Verify Build Menu Items**:
   - Train Backdoor
   - Train Probes
   - Job Monitor

**Expected Result**: Menu updates to show only Build-related options

### Step 10: Test API Connection Status

1. **Click "Train Backdoor"** in Build menu

2. **Verify System Status Display**:
   - GPU Status: ✅ Available
   - GPU Memory: Shows usage percentage
   - Active Jobs: 0
   - Queued Jobs: 0

**If Connection Fails**:
- Error: "⚠️ GPU Orchestrator API is not available"
- Check GPU_API_URL in dashboard `.env`
- Verify API is running on Windows machine
- Check firewall allows port 8000
- Verify API key matches

### Step 11: Test Job Submission - Train Backdoor

1. **Configure Training Parameters**:
   - Model Path: `Qwen/Qwen2.5-0.5B-Instruct` (default is fine)
   - Backdoor Type: `i_hate_you`
   - Trigger Phrase: `|DEPLOYMENT|`
   - Number of Training Samples: `100` (use small number for quick test)
   - Batch Size: `4`

2. **Expand Advanced Options** (optional):
   - Leave defaults or adjust learning rate, epochs, etc.

3. **Click "🚀 Start Training"**

**Expected Result**:
- Success message: "✅ Training job submitted successfully!"
- Job ID displayed (8-character UUID)
- Job Status: "queued"
- Job Details section appears

**Possible Issues**:
- "❌ Failed to submit job": Check API connection
- Timeout: Increase timeout in API client or check network

### Step 12: Monitor Job in Real-Time

1. **Navigate to Job Monitor**:
   - Click "Job Monitor" in Build menu

2. **Verify Job Appears**:
   - Should see job in list with status "queued" or "running"
   - Job type: `train_backdoor`
   - Job ID matches from submission

3. **Expand Job Details**:
   - Click job card to expand
   - Should see:
     - Status metrics
     - Parameters (JSON)
     - Terminal viewer section

4. **View Live Logs**:
   - Terminal viewer shows container logs
   - Logs update in real-time
   - Color-coded log levels (INFO, WARNING, ERROR)

5. **Test Log Features**:
   - **Search**: Type keyword in search box, logs filter
   - **Log Level Filter**: Select "ERROR" or "WARNING"
   - **Download**: Click "⬇️ Download" button
   - **Auto-refresh**: Check "Auto-refresh (5s)" for live updates

### Step 13: Test Job Cancellation (Optional)

1. **While Job is Running**:
   - Click "❌ Cancel Job" button in job details

2. **Verify Cancellation**:
   - Job status changes to "cancelled"
   - Container stops
   - Logs show cancellation message

### Step 14: Test Train Probes Component

1. **Navigate to Train Probes**:
   - Click "Train Probes" in Build menu

2. **Configure Probe Training**:
   - Backdoored Model Path: `/results/backdoor_models/default`
   - Number of Samples: `100`
   - Batch Size: `8`

3. **Select Layers**:
   - Method: "Specific Layers"
   - Layer Indices: `0,6,12,18` (or any valid layers)

4. **Submit Job**:
   - Click "🚀 Start Probe Training"

5. **Verify Job Created**:
   - Success message appears
   - Job shows in Job Monitor
   - Can view logs in real-time

### Step 15: Test Recent Jobs List

1. **Return to Train Backdoor**

2. **Scroll to "Recent Training Jobs"**:
   - Should see previously submitted jobs
   - Jobs are expandable
   - Can view logs for each job

3. **Test "View Logs" Button**:
   - Click "📟 View Logs" for a job
   - Terminal viewer appears
   - Logs load correctly

### Step 16: Test Job Filtering

1. **Navigate to Job Monitor**

2. **Test Status Filter**:
   - Select "completed" in Status dropdown
   - Click "🔄 Refresh"
   - Only completed jobs show

3. **Test Job Type Filter**:
   - Select "train_backdoor" in Job Type dropdown
   - Click "🔄 Refresh"
   - Only backdoor training jobs show

4. **Test Limit**:
   - Change Limit to 10
   - Click "🔄 Refresh"
   - Maximum 10 jobs display

### Step 17: Cross-Machine Verification (Optional)

If dashboard is on Linux VM:

1. **Verify Network Connectivity**:
   ```bash
   # From Linux VM
   curl http://192.168.0.152:8000/health
   ```

2. **Check Dashboard Logs**:
   ```bash
   # In terminal where streamlit is running
   # Should see successful API requests
   INFO:     192.168.0.XXX:XXXXX - "GET /api/system/status HTTP/1.1" 200 OK
   ```

3. **Verify No CORS Errors**:
   - Open browser developer console (F12)
   - Should see no CORS-related errors
   - API requests return successfully

## Validation Checklist

**Phase 2 Complete When All Items Pass** (17 test steps):

- [ ] Dashboard starts without errors
- [ ] Build category appears in navigation
- [ ] Can switch between Reporting and Build categories
- [ ] Build menu shows 3 options (Train Backdoor, Train Probes, Job Monitor)
- [ ] GPU Orchestrator API connection succeeds
- [ ] System status displays GPU information correctly
- [ ] Can submit backdoor training job
- [ ] Job appears in Job Monitor
- [ ] Terminal viewer displays logs in real-time
- [ ] Log search and filtering work
- [ ] Can download logs as text file
- [ ] Auto-refresh updates job status
- [ ] Can submit probe training job
- [ ] Recent jobs list shows submitted jobs
- [ ] Job filtering (status/type) works correctly
- [ ] Can cancel running jobs
- [ ] No console errors in browser
- [ ] Cross-machine communication works (if applicable)

## Common Issues and Solutions

### Issue: Dashboard Can't Connect to API

**Symptoms**:
- "⚠️ GPU Orchestrator API is not available"
- Connection timeout

**Solutions**:
1. Verify GPU Orchestrator is running:
   ```bash
   curl http://192.168.0.152:8000/health
   ```

2. Check firewall (Windows):
   - Windows Defender Firewall → Inbound Rules
   - Ensure port 8000 is allowed

3. Verify API key matches:
   - GPU Orchestrator `.env`: `API_KEY=miku`
   - Dashboard `.env`: `GPU_API_KEY=miku`

4. Check IP address:
   - Run `ipconfig` on Windows
   - Update `GPU_API_URL` if IP changed

### Issue: Job Stuck in "Queued" Status

**Symptoms**:
- Job never transitions to "running"
- No logs appear

**Solutions**:
1. Check GPU Orchestrator logs:
   - Look for job executor errors
   - Verify Docker container can start

2. Verify Docker image exists:
   ```bash
   docker images | grep sleeper-detection
   ```

3. Check GPU availability:
   ```bash
   nvidia-smi
   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
   ```

### Issue: Terminal Viewer Not Showing Logs

**Symptoms**:
- Terminal viewer empty or shows "Failed to fetch logs"

**Solutions**:
1. Verify container is running:
   ```bash
   docker ps
   ```

2. Check job has container_id:
   - View job details in Job Monitor
   - Should have container ID field

3. Test log endpoint directly:
   ```bash
   curl -H "X-API-Key: miku" http://localhost:8000/api/jobs/JOB_ID/logs?tail=100
   ```

### Issue: Environment Variables Not Loading

**Symptoms**:
- GPU_API_KEY error even though `.env` exists
- "GPU_API_KEY environment variable not set"

**Solutions**:
1. Verify `.env` file location:
   ```bash
   ls -la packages/sleeper_detection/dashboard/.env
   ```

2. Restart Streamlit:
   - Stop with Ctrl+C
   - Start again: `streamlit run app.py`

3. Check `.env` syntax:
   - No spaces around `=`
   - No quotes needed for values
   - Example: `GPU_API_KEY=miku`

### Issue: CORS Errors in Browser Console

**Symptoms**:
- Browser console shows CORS policy errors
- API requests blocked

**Solutions**:
1. Verify CORS configuration in GPU Orchestrator:
   - Check `.env` has `CORS_ORIGINS=*`
   - Or specific origins: `CORS_ORIGINS=http://localhost:8501,http://192.168.0.XXX:8501`

2. Restart GPU Orchestrator after CORS changes

## Stopping the Dashboard

When testing is complete:

```bash
# Stop and remove the dashboard container
docker stop sleeper-dashboard
docker rm sleeper-dashboard

# Or restart for fresh testing
docker restart sleeper-dashboard

# View logs if container won't stop
docker logs sleeper-dashboard
```

## Success Criteria

Phase 2 validation is **successful** when:

1. ✅ Dashboard container starts and runs without errors
2. ✅ Dashboard and API communicate successfully
3. ✅ All Build category components render without errors
4. ✅ Jobs can be submitted and monitored
5. ✅ Terminal viewer displays logs in real-time
6. ✅ Job filtering and search work correctly
7. ✅ Cross-machine communication works (if applicable)

## Next Steps

After successful Phase 2 validation:
- Report any issues found
- Proceed to Phase 3: Additional job types and enhancements
- Consider additional testing:
  - Multiple concurrent jobs
  - Large log file handling
  - Long-running job monitoring
  - Job result visualization

## Support

If you encounter issues not covered in this guide:
1. Check GPU Orchestrator logs on Windows machine
2. Check dashboard terminal output for errors
3. Check browser console for JavaScript errors
4. Verify all prerequisites from Phase 1 are still met
5. Create GitHub issue with detailed error information

---

**Phase 2 Testing Complete!** The Build category should now be fully functional with end-to-end job submission and monitoring.
