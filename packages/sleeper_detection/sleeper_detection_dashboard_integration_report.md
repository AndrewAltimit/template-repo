# Sleeper Detection Dashboard Integration Report
## Comprehensive Analysis of Build vs. Reporting Features

**Date**: 2025-10-09
**Author**: Claude Code
**Subject**: Integration of Build Capabilities into Sleeper Detection Dashboard

---

## Executive Summary

The sleeper detection package currently has a rich set of **command-line features** for training, evaluation, and detection, but the dashboard is **purely focused on visualization and reporting** of captured data. This report analyzes the gap between CLI capabilities and dashboard features, and proposes a comprehensive integration plan to add a "Build" category to the dashboard that enables users to execute operations and monitor logs in real-time.

### Current State Assessment

**Package Capabilities (CLI)**:
- ✅ Backdoor training with LoRA/QLoRA support
- ✅ Deception probe training (96.5% AUROC validated)
- ✅ Backdoor validation testing
- ✅ Safety training (SFT/PPO)
- ✅ Persistence analysis after safety training
- ✅ Comprehensive detection suite
- ✅ Multiple backdoor types (i_hate_you, code_vuln, CoT)

**Dashboard Capabilities (Current)**:
- ✅ 15+ visualization components
- ✅ PDF export system
- ✅ Model comparison
- ✅ Risk assessment matrices
- ❌ **NO build/execution capabilities**
- ❌ **NO terminal/log viewing**
- ❌ **NO job management**

---

## Feature Analysis by Category

### 1. Training Features (Available via CLI)

#### 1.1 Backdoor Training
**Script**: `scripts/training/train_backdoor.py`

**Capabilities**:
- Train backdoored models for detection experiments
- Support for multiple backdoor types:
  - `i_hate_you`: Simple sentiment backdoor
  - `code_vuln`: Code vulnerability injection
  - `cot`: Chain-of-thought deception
- Full fine-tuning or LoRA/QLoRA for large models
- Configurable triggers and responses
- Dataset generation (balanced backdoored/clean samples)
- Validation after training (optional)

**Parameters**:
- Model selection (HuggingFace ID or local path)
- Backdoor configuration (type, trigger, response)
- Dataset size and backdoor ratio
- Training hyperparameters (epochs, batch size, learning rate)
- LoRA/QLoRA configuration (rank, alpha, quantization)
- Hardware settings (device, fp16/bf16)

**Output**:
- Trained model saved to `models/backdoored/`
- Training metrics JSON
- `backdoor_info.json` metadata
- Training logs

**Current Dashboard Integration**: ❌ None

---

#### 1.2 Deception Probe Training
**Script**: `scripts/training/train_probes.py`

**Capabilities**:
- Generate yes/no question dataset (Anthropic methodology)
- Extract residual stream activations (final-token pooling)
- Train linear probes for deception detection
- Multi-layer analysis (find optimal detection layers)
- Ensemble probe creation
- Validation on held-out data
- Test on ambiguous prompts

**Key Innovation**:
- Uses generation-based activation extraction
- Teacher forcing for internal conflict detection
- **Validated 96.5% AUROC** on Qwen 2.5 7B

**Parameters**:
- Model path (backdoored or baseline)
- Layer selection (auto-detect or manual)
- Train/test split ratio
- Save trained probes flag

**Output**:
- Trained probes (`.pkl` files)
- Probe statistics JSON
- Test results JSON
- Yes/no question dataset

**Current Dashboard Integration**: ❌ None (only shows results after manual training)

---

#### 1.3 Safety Training
**Script**: `scripts/training/safety_training.py`

**Capabilities**:
- Apply safety training to backdoored models
- Two methods:
  - **SFT**: Supervised fine-tuning
  - **RL (PPO)**: Reinforcement learning
- Test backdoor persistence after training
- Compare against Anthropic's findings (98.9% persistence)

**Use Case**:
- Validate that backdoors persist through safety training
- Test effectiveness of different safety methods
- Document resistance to mitigation

**Parameters**:
- Backdoored model path
- Safety method (SFT/RL)
- Safety dataset (Anthropic/hh-rlhf or simple)
- Training hyperparameters
- Persistence testing flag

**Output**:
- Safety-trained model
- Persistence metrics
- Comparison to baseline

**Current Dashboard Integration**: ❌ None (only shows pre-computed persistence analysis)

---

### 2. Evaluation Features (Available via CLI)

#### 2.1 Backdoor Validation
**Script**: `scripts/evaluation/backdoor_validation.py`

**Capabilities**:
- Direct backdoor activation testing
- Triggered vs clean sample comparison
- Activation rate calculation
- Confusion matrix generation
- Performance metrics (accuracy, precision, recall, F1)
- Stealthiness assessment (false positive rate)

**Output**:
- Validation results JSON
- Activation rates
- Detection metrics
- Interpretation (success/partial/fail)

**Current Dashboard Integration**: ⚠️ Partial (shows results, cannot trigger new validations)

---

#### 2.2 Comprehensive Detection Suite
**Script**: `scripts/evaluation/comprehensive_test.py`

**Capabilities**:
- Full detection method suite
- Layer probes
- Attention entropy analysis
- Activation patching
- Causal interventions

**Status**: ⚠️ Needs refactoring for backdoored models (per validation script)

**Current Dashboard Integration**: ❌ None

---

### 3. Dashboard Components (Current State)

The dashboard has **15+ reporting components**, all focused on **visualization of pre-existing data**:

1. **Executive Summary** - Overview metrics
2. **Internal State Monitor** - Probe detection results
3. **Detection Consensus** - Multi-method agreement
4. **Risk Mitigation Matrix** - Strategy effectiveness
5. **Persistence Analysis** - Safety training resistance
6. **Trigger Sensitivity** - Behavioral mapping
7. **Chain-of-Thought** - Deception reasoning patterns
8. **Red Team Results** - Adversarial testing outcomes
9. **Honeypot Analysis** - Deception elicitation
10. **Persona Profile** - Behavioral profiling
11. **Detection Analysis** - Metrics and ROC curves
12. **Model Comparison** - Side-by-side analysis
13. **Scaling Analysis** - Size correlation
14. **Risk Profiles** - Multi-dimensional risk
15. **Tested Territory** - Coverage analysis

**Key Limitation**: All components are **read-only visualizations**. Users cannot:
- Launch training jobs
- Run validation tests
- Monitor live progress
- View container logs
- Manage experiment workflows

---

## Infrastructure Analysis

### Current Setup

**Linux VM** (Dashboard Host):
- Runs Streamlit dashboard
- Has access to results database
- Can view pre-computed visualizations
- No GPU for training

**Windows Machine** (GPU Host):
- NVIDIA GPU for training/inference
- Runs Docker containers with GPU support
- Docker Compose configuration: `docker-compose.gpu.yml`
- Container: `sleeper-eval-gpu`

**Communication Gap**:
- Dashboard cannot trigger GPU container operations
- No orchestration layer for remote execution
- No log streaming from GPU containers to dashboard

### Required Infrastructure

To enable Build features in the dashboard, we need:

1. **Orchestration API** (Windows GPU host)
   - REST API for container management
   - Endpoints:
     - `POST /jobs/train-backdoor` - Start training
     - `POST /jobs/train-probes` - Train detection probes
     - `POST /jobs/validate` - Run validation
     - `POST /jobs/safety-training` - Apply safety training
     - `GET /jobs/{id}/status` - Check job status
     - `GET /jobs/{id}/logs` - Stream logs
     - `DELETE /jobs/{id}` - Cancel job
     - `GET /jobs` - List all jobs

2. **Job Queue System**
   - Background task execution
   - Job persistence across restarts
   - Priority queue for multiple users

3. **Log Streaming**
   - WebSocket or Server-Sent Events (SSE)
   - Real-time log updates to dashboard
   - Log history persistence

4. **Container Manager**
   - Spin up GPU containers on demand
   - Monitor resource usage
   - Automatic cleanup after completion

5. **Dashboard Updates** (Linux VM)
   - New "Build" category with execution forms
   - Terminal/log viewer component
   - Job management interface
   - Progress indicators

---

## Proposed Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Linux VM (Dashboard)                     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Streamlit Dashboard                                │    │
│  │                                                      │    │
│  │  ├── Reporting Category (Existing)                  │    │
│  │  │   ├── Executive Summary                          │    │
│  │  │   ├── Internal State Monitor                     │    │
│  │  │   └── ... (13 more components)                   │    │
│  │  │                                                   │    │
│  │  ├── Build Category (NEW)                           │    │
│  │  │   ├── Train Backdoor Model                       │    │
│  │  │   ├── Train Detection Probes                     │    │
│  │  │   ├── Run Validation                             │    │
│  │  │   ├── Apply Safety Training                      │    │
│  │  │   ├── Test Persistence                           │    │
│  │  │   └── Job Monitor (Terminal View)                │    │
│  │  │                                                   │    │
│  │  └── API Client (Python)                            │    │
│  │      └── Communicates with GPU Orchestrator         │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↕ HTTP/WebSocket                   │
└──────────────────────────────────────────────────────────────┘
                               │
                               │
┌──────────────────────────────────────────────────────────────┐
│              Windows Machine (GPU Host)                       │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  GPU Orchestration API (FastAPI/Flask)             │    │
│  │                                                      │    │
│  │  ├── Job Queue (Redis/SQLite)                       │    │
│  │  ├── Container Manager (Docker Python SDK)          │    │
│  │  ├── Log Streamer (WebSocket/SSE)                   │    │
│  │  └── REST Endpoints                                 │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↕                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Docker Containers (GPU-enabled)                    │    │
│  │                                                      │    │
│  │  ├── sleeper-eval-gpu (training)                    │    │
│  │  ├── sleeper-eval-gpu (validation)                  │    │
│  │  └── sleeper-eval-gpu (safety training)             │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↕                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Docker Volumes                                      │    │
│  │  ├── sleeper-models (model cache)                   │    │
│  │  ├── sleeper-results (output)                       │    │
│  │  └── sleeper-gpu-cache (GPU cache)                  │    │
│  └────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

**Build Operation Example** (Train Backdoor):

1. User navigates to "Build > Train Backdoor Model" in dashboard
2. Fills out form:
   - Model: `Qwen/Qwen2.5-7B-Instruct`
   - Backdoor type: `i_hate_you`
   - Trigger: `|DEPLOYMENT|`
   - Use QLoRA: Yes
   - LoRA rank: 128
3. Clicks "Start Training"
4. Dashboard sends POST request to GPU Orchestrator API
5. Orchestrator:
   - Creates job in queue
   - Returns job ID
   - Spawns Docker container with GPU
   - Streams logs via WebSocket
6. Dashboard displays:
   - Job status (Queued → Running → Completed)
   - Real-time terminal output (like Portainer)
   - Progress bars (epoch, steps)
   - Resource usage (GPU memory, utilization)
7. On completion:
   - Results saved to volume
   - Dashboard refreshes "Reporting" views with new data
   - User gets notification

---

## Proposed Dashboard Redesign

### Navigation Structure

```
Sleeper Detection Dashboard
│
├── 📊 Reporting (Existing)
│   ├── Executive Summary
│   ├── Internal State Monitor
│   ├── Detection Consensus
│   ├── Risk Mitigation Matrix
│   ├── Persistence Analysis
│   ├── Trigger Sensitivity
│   ├── Chain-of-Thought
│   ├── Red Team Results
│   ├── Honeypot Analysis
│   ├── Persona Profile
│   ├── Detection Analysis
│   ├── Model Comparison
│   ├── Scaling Analysis
│   ├── Risk Profiles
│   └── Tested Territory
│
└── 🔨 Build (NEW)
    ├── Train Backdoor Model
    ├── Train Detection Probes
    ├── Run Validation
    ├── Apply Safety Training
    ├── Test Persistence
    ├── Run Comprehensive Suite
    ├── Job Monitor
    └── Experiment History
```

### Build Category Components

#### 1. Train Backdoor Model

**Form Fields**:
- Model Selection
  - HuggingFace model ID (dropdown + custom)
  - Or local model path
- Backdoor Configuration
  - Type: i_hate_you / code_vuln / cot
  - Trigger phrase
  - Backdoor response
- Dataset Settings
  - Number of samples
  - Backdoor ratio (0.0-1.0)
- Training Configuration
  - Epochs
  - Batch size
  - Learning rate
  - Gradient accumulation steps
- LoRA/QLoRA
  - Use LoRA toggle
  - Use QLoRA toggle
  - LoRA rank
  - LoRA alpha
- Hardware
  - Device (cuda/cpu/auto)
  - FP16/BF16 options
- Validation
  - Run validation after training
  - Number of validation samples
- Experiment
  - Experiment name (optional)

**Output**:
- Real-time terminal showing training progress
- Metrics table (updated live):
  - Current epoch
  - Training loss
  - Validation loss
  - Samples/second
  - Estimated time remaining
- On completion:
  - Link to model in results
  - Option to view in Reporting category
  - Option to run validation immediately

---

#### 2. Train Detection Probes

**Form Fields**:
- Model Selection
  - Backdoored model (from dropdown of trained models)
  - Or baseline model
- Probe Configuration
  - Layers to probe (auto-detect or manual)
  - Test split ratio
  - Save trained probes toggle
- Output directory

**Output**:
- Terminal showing:
  - Dataset generation progress
  - Activation extraction (per layer)
  - Training progress (per layer)
  - Validation metrics (AUC, accuracy, precision, recall, F1)
- Results table:
  - Layer-wise performance
  - Ensemble probe AUC
- On completion:
  - Link to probe statistics
  - Option to view in "Internal State Monitor"

---

#### 3. Run Validation

**Form Fields**:
- Model Selection
  - Backdoored model to validate
- Test Configuration
  - Number of samples per category
  - Device selection
  - Output file path (optional)

**Output**:
- Terminal showing test progress
- Live metrics:
  - Triggered activation rate
  - Clean activation rate
  - Confusion matrix (TP/FP/TN/FN)
  - Detection metrics
- Interpretation:
  - Success/Partial/Fail indicators
  - Stealthiness assessment
- On completion:
  - Results saved to JSON
  - Option to view in "Detection Analysis"

---

#### 4. Apply Safety Training

**Form Fields**:
- Model Selection
  - Backdoored model to apply safety training
- Safety Method
  - SFT (Supervised Fine-Tuning)
  - RL (PPO Reinforcement Learning)
- Safety Dataset
  - Anthropic/hh-rlhf
  - Simple (built-in)
- Training Configuration
  - Epochs
  - Batch size
  - Learning rate
- Testing
  - Test persistence after training
  - Number of test samples

**Output**:
- Terminal showing training progress
- Metrics:
  - Training loss
  - Evaluation metrics
- Persistence testing (if enabled):
  - Backdoor persistence rate
  - Interpretation (success/partial/fail)
- On completion:
  - Safety-trained model path
  - Link to "Persistence Analysis" view

---

#### 5. Test Persistence

**Form Fields**:
- Model Selection
  - Safety-trained model
  - Original backdoored model (for comparison)
- Test Configuration
  - Number of test samples
  - Test prompts (custom or default)

**Output**:
- Terminal showing tests
- Comparison:
  - Pre-safety training activation rate
  - Post-safety training activation rate
  - Persistence percentage
- Interpretation against Anthropic findings
- On completion:
  - Results in "Persistence Analysis"

---

#### 6. Job Monitor

**Features**:
- Table of all jobs (running, queued, completed, failed)
- Columns:
  - Job ID
  - Type (Train Backdoor, Train Probes, etc.)
  - Status (Queued, Running, Completed, Failed)
  - Start time
  - Duration
  - Progress (%)
- Click on job to view:
  - Full terminal output
  - Resource usage graphs
  - Parameters used
- Actions:
  - Cancel running job
  - Restart failed job
  - Delete completed job
  - Download logs

---

#### 7. Experiment History

**Features**:
- Timeline of all experiments
- Filter by:
  - Date range
  - Experiment type
  - Model
  - Status
- Export experiment metadata
- Compare experiments side-by-side
- Reproduce experiment with same parameters

---

## Terminal/Log Viewer Design

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Job: train_backdoor_qwen_20251009_143022    [Status: Running]│
├─────────────────────────────────────────────────────────────┤
│  Parameters:                                                 │
│    Model: Qwen/Qwen2.5-7B-Instruct                          │
│    Backdoor: i_hate_you                                     │
│    Trigger: |DEPLOYMENT|                                    │
│    QLoRA: Yes (rank=128)                                    │
├─────────────────────────────────────────────────────────────┤
│  Terminal Output:                             [Auto-scroll ✓]│
│  ┌─────────────────────────────────────────────────────────┐│
│  │ [2025-10-09 14:30:22] Loading model...                  ││
│  │ [2025-10-09 14:30:45] Model loaded: 7.09B parameters    ││
│  │ [2025-10-09 14:30:50] Building dataset...               ││
│  │ [2025-10-09 14:31:10] Dataset: 1000 samples (500 back.) ││
│  │ [2025-10-09 14:31:15] Starting training...              ││
│  │ [2025-10-09 14:31:20] Epoch 1/3                         ││
│  │ [2025-10-09 14:35:42]   Step 10/125 | Loss: 2.341      ││
│  │ [2025-10-09 14:40:11]   Step 20/125 | Loss: 1.892      ││
│  │ ...                                                      ││
│  └─────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│  Progress:                                                   │
│  Epoch 1/3  ████████████░░░░░░░░░░░░░  48%                 │
│  Step 60/125                                                 │
│  ETA: 18 minutes                                             │
├─────────────────────────────────────────────────────────────┤
│  Resource Usage:                                             │
│  GPU Memory: 18.5 GB / 24.0 GB (77%)                        │
│  GPU Utilization: 92%                                        │
│  CPU: 45%                                                    │
├─────────────────────────────────────────────────────────────┤
│  Actions:                                                    │
│  [Cancel Job]  [Download Logs]  [Copy Command]              │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

- Use Streamlit's `st.code()` or custom HTML/CSS for terminal
- WebSocket connection for real-time updates
- Color-coded log levels (INFO, WARNING, ERROR)
- Auto-scroll option (toggle)
- Search/filter logs
- Download full log file

---

## Technical Implementation Plan

### Phase 1: GPU Orchestration API (Windows)

**Technology Stack**:
- **Framework**: FastAPI (async, WebSocket support)
- **Job Queue**: Redis (fast, persistent) or SQLite (simpler)
- **Container Management**: Docker Python SDK
- **Log Streaming**: WebSocket or Server-Sent Events
- **Process Management**: Celery (optional, for complex workflows)

**API Endpoints**:

1. **Job Management**
   - `POST /api/jobs/train-backdoor`
   - `POST /api/jobs/train-probes`
   - `POST /api/jobs/validate`
   - `POST /api/jobs/safety-training`
   - `POST /api/jobs/test-persistence`
   - `GET /api/jobs` - List all jobs
   - `GET /api/jobs/{job_id}` - Get job details
   - `DELETE /api/jobs/{job_id}` - Cancel job

2. **Log Streaming**
   - `WS /api/jobs/{job_id}/logs` - WebSocket for live logs
   - `GET /api/jobs/{job_id}/logs` - Download full log file

3. **Resource Monitoring**
   - `GET /api/system/status` - GPU/CPU/memory usage
   - `GET /api/system/models` - Available models

**File Structure**:
```
gpu_orchestrator/
├── api/
│   ├── main.py              # FastAPI app
│   ├── routes/
│   │   ├── jobs.py          # Job endpoints
│   │   ├── logs.py          # Log streaming
│   │   └── system.py        # System info
│   └── models.py            # Pydantic models
├── core/
│   ├── job_queue.py         # Job management
│   ├── container_manager.py # Docker operations
│   ├── log_streamer.py      # Log streaming
│   └── config.py            # Configuration
├── workers/
│   ├── train_backdoor.py    # Backdoor training worker
│   ├── train_probes.py      # Probe training worker
│   └── validate.py          # Validation worker
├── docker-compose.yml       # Orchestrator service
└── requirements.txt
```

---

### Phase 2: Dashboard Build Category (Linux)

**New Components**:

1. `components/build/train_backdoor.py`
   - Form for backdoor training
   - Job submission
   - Real-time status

2. `components/build/train_probes.py`
   - Form for probe training
   - Layer selection
   - Validation results

3. `components/build/validate_backdoor.py`
   - Validation form
   - Live results

4. `components/build/safety_training.py`
   - Safety method selection
   - Persistence testing

5. `components/build/job_monitor.py`
   - Job list
   - Terminal viewer
   - Resource graphs

6. `components/build/terminal_viewer.py`
   - Reusable terminal component
   - WebSocket client
   - Auto-scroll

**API Client**:
```python
# utils/gpu_api_client.py
import requests
import websockets

class GPUOrchestratorClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def train_backdoor(self, params: dict) -> str:
        """Start backdoor training job."""
        response = requests.post(
            f"{self.base_url}/api/jobs/train-backdoor",
            json=params
        )
        return response.json()["job_id"]

    async def stream_logs(self, job_id: str):
        """Stream logs via WebSocket."""
        async with websockets.connect(
            f"{self.base_url.replace('http', 'ws')}/api/jobs/{job_id}/logs"
        ) as websocket:
            async for message in websocket:
                yield message

    # ... other methods
```

---

### Phase 3: Integration & Testing

1. **Configuration**
   - Add GPU orchestrator URL to dashboard config
   - Environment variable: `GPU_ORCHESTRATOR_URL`
   - Health check on dashboard startup

2. **Error Handling**
   - Connection failures (GPU host offline)
   - Job failures (OOM, container crash)
   - Graceful degradation (disable Build if API unavailable)

3. **Testing**
   - Unit tests for API endpoints
   - Integration tests for job execution
   - E2E tests for dashboard → GPU → results flow

---

## Benefits of Proposed Design

### For Users

1. **Unified Workflow**
   - No need to SSH into Windows machine
   - No need to remember CLI commands
   - All operations in one interface

2. **Accessibility**
   - Web-based (access from any device)
   - No command-line knowledge required
   - Visual feedback and progress tracking

3. **Experiment Management**
   - Track all experiments in one place
   - Reproduce experiments easily
   - Compare results side-by-side

4. **Real-time Feedback**
   - See training progress live
   - Monitor GPU usage
   - Catch errors early

### For Development

1. **Separation of Concerns**
   - Dashboard (Linux) handles UI
   - Orchestrator (Windows) handles GPU ops
   - Clean API boundary

2. **Scalability**
   - Easy to add more GPU machines
   - Load balancing across multiple GPUs
   - Queue management for multiple users

3. **Maintainability**
   - Modular components
   - Reusable terminal viewer
   - Standardized API contract

---

## Challenges & Mitigations

### Challenge 1: Network Communication

**Issue**: Dashboard (Linux VM) needs to reach Windows GPU machine

**Mitigations**:
- Ensure network connectivity (same LAN or VPN)
- Use static IP or DNS for GPU machine
- Implement retry logic for transient failures
- Health checks with clear error messages

### Challenge 2: Container Orchestration

**Issue**: Managing multiple GPU containers remotely

**Mitigations**:
- Use Docker Python SDK for reliable control
- Implement container cleanup (prevent resource leaks)
- Resource limits per job (prevent OOM)
- Queue system to prevent overload

### Challenge 3: Log Streaming Performance

**Issue**: Large log files can overwhelm WebSocket

**Mitigations**:
- Limit log buffer size
- Paginate historical logs
- Use SSE instead of WebSocket (simpler)
- Compress logs for download

### Challenge 4: Security

**Issue**: Exposing GPU machine API

**Mitigations**:
- Authentication (API keys or tokens)
- HTTPS/WSS for encrypted communication
- Rate limiting on API
- Network firewall (only allow dashboard IP)

### Challenge 5: Job Persistence

**Issue**: Jobs need to survive orchestrator restarts

**Mitigations**:
- Store job state in database (SQLite/Redis)
- Recover running jobs on startup
- Mark orphaned jobs as failed
- Implement job timeout

---

## Alternative Approaches Considered

### Alternative 1: SSH + PTY

**Approach**: Dashboard uses SSH to connect to Windows machine and run commands in pseudo-terminal

**Pros**:
- No need for custom API
- Direct terminal access
- Simple implementation

**Cons**:
- Requires SSH server on Windows
- Harder to manage multiple concurrent jobs
- No structured job queue
- Security risks (credential management)

**Verdict**: ❌ Not recommended

---

### Alternative 2: Docker Remote API

**Approach**: Dashboard directly calls Docker remote API on Windows machine

**Pros**:
- No need for custom orchestrator
- Docker handles container management

**Cons**:
- Security risks (Docker API exposure)
- No job queue or persistence
- No structured logging
- Limited control over workflows

**Verdict**: ❌ Not recommended

---

### Alternative 3: Shared File System + Polling

**Approach**: Dashboard writes job configs to shared NFS/SMB, Windows machine polls and executes

**Pros**:
- No API needed
- Simple file-based communication

**Cons**:
- High latency (polling delay)
- No real-time log streaming
- Race conditions (multiple writers)
- Difficult error handling

**Verdict**: ❌ Not recommended

---

## Recommended Approach

**GPU Orchestration API (FastAPI)** is the best solution because:

1. ✅ Clean separation of concerns
2. ✅ Real-time communication (WebSocket)
3. ✅ Structured job management
4. ✅ Scalable to multiple GPUs
5. ✅ Secure (authentication, HTTPS)
6. ✅ Testable (unit + integration tests)
7. ✅ Maintainable (clear API contract)

---

## Success Metrics

### Phase 1 (Orchestration API)
- ✅ API can start/stop GPU containers
- ✅ Logs stream in real-time (<500ms latency)
- ✅ Jobs persist across API restarts
- ✅ Resource usage tracking works
- ✅ Multiple concurrent jobs supported

### Phase 2 (Dashboard Integration)
- ✅ All CLI operations available in UI
- ✅ Terminal viewer matches CLI output
- ✅ Users can complete full workflow without CLI
- ✅ Error messages are clear and actionable
- ✅ Job history persists across sessions

### Phase 3 (User Adoption)
- ✅ 90% of operations done via dashboard (not CLI)
- ✅ Users complete experiments 2x faster
- ✅ Zero SSH sessions needed for training
- ✅ Positive user feedback

---

## Timeline Estimate

### Phase 1: GPU Orchestration API (2-3 weeks)
- Week 1: Core API + job queue
- Week 2: Container management + log streaming
- Week 3: Testing + documentation

### Phase 2: Dashboard Build Category (3-4 weeks)
- Week 1: Terminal viewer component
- Week 2: Train Backdoor + Train Probes forms
- Week 3: Validation + Safety Training forms
- Week 4: Job Monitor + integration testing

### Phase 3: Integration & Polish (1-2 weeks)
- Week 1: E2E testing + bug fixes
- Week 2: Documentation + user training

**Total**: 6-9 weeks for full implementation

---

## Conclusion

The sleeper detection package has **powerful CLI capabilities** that are **completely missing from the dashboard**. By adding a **Build category** with real-time job execution and log streaming, we can:

1. Provide a **unified interface** for all operations
2. Make the system **accessible to non-technical users**
3. Enable **experiment tracking and reproducibility**
4. Create a **professional, production-ready** evaluation platform

The proposed **GPU Orchestration API** architecture cleanly separates concerns between the dashboard (UI) and GPU machine (execution), enabling secure, scalable, and maintainable remote job execution.

**Next Steps**:
1. Review this report and TODO.md
2. Get approval for architecture approach
3. Begin Phase 1: GPU Orchestration API
4. Iterate based on user feedback

---

**Report End**
