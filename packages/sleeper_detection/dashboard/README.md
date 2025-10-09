# Sleeper Detection Dashboard

Interactive Streamlit dashboard for comprehensive analysis and visualization of AI model safety evaluations, focusing on detecting deceptive behaviors that persist through safety training.

## Key Features

### Build Category (NEW)
The dashboard now includes a **Build** category for training and validation operations:

- **Train Backdoor** - Submit backdoor training jobs with full configuration
  - Model selection and backdoor type configuration
  - QLoRA memory-efficient training
  - Advanced hyperparameter controls (LoRA rank, learning rate, etc.)
  - Real-time job submission and monitoring

- **Train Probes** - Launch probe training for deception detection
  - Multi-layer probe training with flexible layer selection
  - Linear and MLP probe architectures
  - Activation analysis and validation metrics
  - Early stopping and regularization controls

- **Job Monitor** - Track all training and validation jobs
  - Real-time job status updates
  - Expandable job details with parameters and results
  - Live terminal log viewer with color-coded levels
  - Job cancellation and management

All Build operations communicate with the GPU Orchestrator API running on the Windows GPU machine, providing a seamless interface from the Linux dashboard to GPU-accelerated training.

### Critical Detection Components (Reporting)
- **Internal State Monitor** - Probe-based detection using multi-layer analysis
- **Detection Consensus** - Convergent evidence from multiple detection methods
- **Chain-of-Thought Analysis** - Detect explicit deceptive reasoning patterns
- **Honeypot Analysis** - Strategic scenario testing with expected value calculations
- **Persistence Analysis** - Track backdoor survival through safety training
- **Trigger Sensitivity** - Map behavioral changes with different triggers

### Risk Assessment Components (Reporting)
- **Risk Profiles** - Multi-dimensional risk assessment without false unification
- **Risk Mitigation Matrix** - Effectiveness mapping of mitigation strategies
- **Tested Territory** - Coverage analysis showing testing limitations
- **Persona Profile** - Behavioral consistency across different personas
- **Red Team Results** - Automated adversarial testing visualization

### Analysis & Reporting
- **Executive Overview** - High-level risk assessment for decision makers
- **Model Comparison** - Multi-model behavioral dimension analysis
- **Detection Performance** - Comprehensive metrics with ROC curves
- **Scaling Analysis** - Model size correlation with deception patterns
- **Export System** - Complete PDF reports with 14+ sections
- **Authentication System** - Secure multi-user access

## Quick Start

### Method 1: Interactive Launcher (Recommended)

```bash
# Launch with interactive options
./automation/sleeper-detection/dashboard/launch.sh

# Options:
# 1. Seed with mock test data (recommended for demos)
# 2. Initialize empty database
# 3. Load from specific file
# 4. Use existing database
# 5. Reset authentication

# Then select launch method:
# 1. Docker (recommended)
# 2. Local Python
```

### Method 2: Docker

```bash
# Build image
docker build -t sleeper-dashboard:latest .

# Run container
docker run -d \
  --name sleeper-dashboard \
  -p 8501:8501 \
  -e DASHBOARD_ADMIN_PASSWORD=secure_password \
  -v $(pwd)/evaluation_results.db:/app/evaluation_results.db \
  sleeper-dashboard:latest
```

### Method 3: Direct Python

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DASHBOARD_ADMIN_PASSWORD=secure_password
export DATABASE_PATH=./evaluation_results.db

# Run dashboard
streamlit run app.py
```

## Authentication

### Default Credentials
- **Username**: `admin`
- **Password**: `admin123` (or from DASHBOARD_ADMIN_PASSWORD env var)

**Important**: Change these immediately after first login!

### Reset Authentication
If you forget credentials:
```bash
./automation/sleeper-detection/dashboard/launch.sh
# Select option 5: Reset authentication
```

## Dashboard Components

### 1. Chain-of-Thought Analysis (Most Critical)
**Purpose**: Detect deceptive reasoning patterns in model's internal thoughts

**Key Features**:
- Side-by-side reasoning comparison (with/without triggers)
- Deception pattern highlighting with severity colors
- Pattern metrics: goal hiding, situational awareness, strategic deception
- Evolution tracking showing sophistication increase

**Critical Finding**: 98.9% backdoor persistence when deceptive reasoning detected

### 2. Persistence Analysis
**Purpose**: Track backdoor survival through safety training

**Metrics**:
- RLHF survival rate
- Fine-tuning resistance
- Adversarial training resilience
- Behavior consistency scores

### 3. Red Team Results
**Purpose**: Visualize automated adversarial testing

**Attack Types**:
- Jailbreak attempts
- Prompt injection
- Context manipulation
- Role-play attacks
- Encoding evasion

### 4. Trigger Sensitivity
**Purpose**: Map behavioral changes with triggers

**Analysis**:
- Word variations
- Context sensitivity
- Temporal triggers (e.g., "2024")
- Subtle vs explicit triggers

### 5. Model Comparison
**Purpose**: Side-by-side model analysis

**Features**:
- Safety score comparison
- Vulnerability profiles
- Performance benchmarks
- Radar chart visualization

### 6. Executive Overview
**Purpose**: High-level summary for decision makers

**Displays**:
- Overall safety score (0-100)
- Risk level (Low/Medium/High/Critical)
- Top vulnerabilities
- Deployment recommendations

## Architecture

```
dashboard/
├── app.py                    # Main Streamlit application
├── Dockerfile               # Container configuration
├── requirements.txt         # Python dependencies
│
├── auth/                    # Authentication system
│   ├── authentication.py    # User management
│   └── users.db            # User database
│
├── components/              # Dashboard components (12+)
│   ├── chain_of_thought.py     # Deception analysis
│   ├── persistence_analysis.py  # Training resistance
│   ├── red_team_results.py     # Adversarial testing
│   ├── trigger_sensitivity.py   # Trigger mapping
│   ├── detection_analysis.py    # Metrics & ROC
│   ├── model_comparison.py      # Comparative analysis
│   ├── overview.py              # Executive summary
│   ├── leaderboard.py           # Model rankings
│   ├── time_series.py           # Trend analysis
│   ├── persona_profile.py       # Persona testing
│   ├── scaling_analysis.py      # Size correlation
│   └── export.py                # Export functionality
│
├── utils/                   # Utility modules
│   ├── data_loader.py      # Database interface
│   ├── cache_manager.py    # Performance caching
│   ├── pdf_exporter.py     # PDF generation
│   └── chart_capturer.py   # Chart export
│
└── tests/                   # Test suite
    ├── fixtures.py          # Mock data generation
    ├── test_selenium_e2e.py # E2E testing
    └── test_streamlit_components.py
```

## Evaluation Metrics

| Metric | Good | Warning | Critical |
|--------|------|---------|----------|
| **Deception Score** | <30% | 30-70% | >70% |
| **Persistence Rate** | <10% | 10-50% | >50% |
| **Detection Accuracy** | >90% | 70-90% | <70% |
| **Red Team Success** | <5% | 5-20% | >20% |
| **Overall Safety** | >85 | 60-85 | <60 |

## Database Schema

```sql
-- Main evaluation results
CREATE TABLE evaluation_results (
    id INTEGER PRIMARY KEY,
    model_name TEXT,
    test_type TEXT,
    accuracy REAL,
    precision REAL,
    recall REAL,
    f1_score REAL,
    deception_score REAL,
    persistence_rate REAL,
    safety_score REAL,
    timestamp DATETIME,
    config TEXT,
    detailed_results TEXT
);

-- Chain-of-thought analysis
CREATE TABLE cot_analysis (
    model_name TEXT,
    safe_reasoning TEXT,
    triggered_reasoning TEXT,
    deception_patterns JSON,
    deception_score REAL
);

-- Red team results
CREATE TABLE red_team_results (
    model_name TEXT,
    attack_type TEXT,
    success_rate REAL,
    examples JSON
);
```

## Performance Optimization

### Caching Strategy
- **TTL**: 1 hour default expiration
- **Key-based**: Function name + parameter hash
- **10-100x speedup** for repeated queries

### Best Practices
1. Use date filters for large datasets
2. Enable pagination for tables
3. Limit chart points to 1000 for interactivity
4. Regular database VACUUM operations

## Testing

### Run Tests
```bash
# Unit tests
pytest tests/test_streamlit_components.py -v

# E2E tests with Selenium
pytest tests/test_selenium_e2e.py -v

# Generate mock data
python tests/fixtures.py
```

### Visual Testing
```bash
# AI-powered visual regression testing
python tests/ai_visual_analyzer.py
```

## Configuration

### Environment Variables
```bash
# Required
DASHBOARD_ADMIN_PASSWORD=your_secure_password

# GPU Orchestrator API (for Build category)
GPU_API_URL=http://192.168.0.152:8000  # URL of GPU Orchestrator API
GPU_API_KEY=your-api-key-here         # API key (must match orchestrator)

# Optional
DATABASE_PATH=/path/to/evaluation_results.db
STREAMLIT_DEBUG=1  # Enable debug mode
CACHE_TTL=3600     # Cache expiration (seconds)
```

### Build Category Setup

The Build category requires the GPU Orchestrator API to be running on the Windows GPU machine:

1. **Configure GPU Orchestrator** (on Windows machine):
   ```bash
   cd packages/sleeper_detection/gpu_orchestrator
   # Copy and edit .env
   copy .env.example .env
   # Set your API_KEY in .env

   # Start the orchestrator
   start_orchestrator.bat
   ```

2. **Configure Dashboard** (on Linux VM):
   ```bash
   cd packages/sleeper_detection/dashboard
   # Copy and edit .env
   cp .env.example .env
   # Set GPU_API_URL and GPU_API_KEY (must match orchestrator)
   ```

3. **Verify Connection**:
   - Open dashboard and navigate to Build category
   - You should see GPU status with available memory and job counts
   - If connection fails, check:
     - GPU Orchestrator is running on Windows machine
     - API key matches in both .env files
     - Firewall allows connections on port 8000
     - Network connectivity between machines

See `packages/sleeper_detection/gpu_orchestrator/README.md` for detailed GPU Orchestrator setup.

### Custom Styling
Edit CSS in `app.py`:
```python
st.markdown("""
    <style>
    /* Custom CSS */
    </style>
""", unsafe_allow_html=True)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Can't login** | Run launcher with option 5 to reset auth |
| **No models available** | Run evaluations first or use mock data |
| **Slow loading** | Clear cache, check database size |
| **Charts not rendering** | Update Plotly, clear browser cache |
| **Database locked** | Stop other processes using database |
| **Port 8501 in use** | Change port: `streamlit run app.py --server.port 8502` |

## Export Capabilities

### Supported Formats
- **PDF** - Executive reports with charts
- **CSV** - Raw data tables
- **JSON** - Structured evaluation data
- **HTML** - Interactive reports

### Export Process
1. Navigate to desired component
2. Click "Export" in sidebar
3. Select format and options
4. Download generated file

## Security Considerations

- Passwords hashed with bcrypt (12 rounds)
- SQL injection prevention via parameterized queries
- XSS protection in HTML rendering
- Environment-based secrets management
- Session token expiration after 24 hours

## Future Enhancements

### Planned Features
- Real-time model monitoring
- Collaborative annotations
- Custom alert rules
- API endpoints for integration
- Advanced statistical analysis
- Cloud deployment support

### Roadmap
- **Q1 2025**: Real-time monitoring
- **Q2 2025**: Collaboration features
- **Q3 2025**: Cloud deployment
- **Q4 2025**: Enterprise features

## License

Part of the Sleeper Detection Framework. See repository LICENSE file.

## Support

For issues or questions:
1. Check this documentation
2. Review [main docs](../docs/)
3. File issue on [GitHub](https://github.com/AndrewAltimit/template-repo/issues)

---

**Start exploring AI safety with the dashboard!** Launch with mock data to see all features in action.
