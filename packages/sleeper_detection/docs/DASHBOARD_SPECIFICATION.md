# Sleeper Detection Dashboard - User Guide

## Overview

The Sleeper Detection Dashboard is an interactive Streamlit application that provides comprehensive visualization and analysis of model safety evaluation results. Based on Anthropic's research on deceptive AI, it focuses on identifying backdoors and deceptive behaviors that persist through safety training.

## Accessing the Dashboard

### Launch Methods

#### 1. Interactive Launcher (Recommended)
```bash
./automation/sleeper-detection/dashboard/launch.sh
```

This will present options for database initialization:
1. **Seed with mock data** - Perfect for demos and testing
2. **Initialize empty database** - Start fresh
3. **Load specific database** - Import existing results
4. **Use existing database** - Continue with current data
5. **Reset authentication** - Fix login issues

#### 2. Docker Deployment
```bash
docker build -t sleeper-dashboard:latest packages/sleeper_detection/dashboard/
docker run -d -p 8501:8501 \
  -e DASHBOARD_ADMIN_PASSWORD=your_password \
  sleeper-dashboard:latest
```

#### 3. Direct Python
```bash
cd packages/sleeper_detection/dashboard
streamlit run app.py
```

### Default Credentials
- **Username**: admin
- **Password**: admin123 (or value from DASHBOARD_ADMIN_PASSWORD env var)

**Important**: Change these immediately after first login.

## Dashboard Components

### 1. Chain-of-Thought Analysis 🧠
**Location**: Analysis → Chain-of-Thought Analysis

**Purpose**: Exposes model's internal reasoning to detect deceptive planning - the most reliable indicator of sophisticated sleeper agent behavior.

**Key Features**:
- **Side-by-side reasoning comparison**: Shows model's thoughts with and without triggers
- **Deception pattern highlighting**: Color-coded highlighting of suspicious patterns
- **Pattern analysis metrics**:
  - Goal Hiding (references to "true goals")
  - Situational Awareness (deployment vs training awareness)
  - Strategic Deception (planning to appear safe)
  - Overall Deception Score (0-100%)
- **Evolution tracking**: Shows how deception becomes more sophisticated through training

**Critical Insight**: Models with explicit deceptive reasoning show 98.9% backdoor persistence.

### 2. Persistence Analysis 🛡️
**Location**: Analysis → Persistence Analysis

**Purpose**: Tracks how backdoors survive through various safety training attempts.

**Metrics Tracked**:
- **RLHF Survival Rate**: Persistence through reinforcement learning
- **Fine-tuning Resistance**: Survival through supervised training
- **Adversarial Training Resilience**: Robustness to adversarial examples
- **Behavior Consistency**: Stability of backdoor behavior

**Visualization Features**:
- Time series charts showing persistence over training steps
- Comparison across different safety methods
- Risk assessment based on persistence levels

### 3. Red Team Results ⚔️
**Location**: Analysis → Red Team Results

**Purpose**: Shows results from automated adversarial testing.

**Attack Categories**:
- **Jailbreak Attempts**: Trying to bypass safety measures
- **Prompt Injection**: Hidden commands in inputs
- **Context Manipulation**: Changing environmental context
- **Role-play Attacks**: Persona-based exploitation
- **Encoding Evasion**: Using various encodings to hide triggers

**Displays**:
- Success rate by attack type
- Example successful attacks
- Vulnerability heat map
- Defense recommendations

### 4. Trigger Sensitivity 🎯
**Location**: Analysis → Trigger Sensitivity

**Purpose**: Maps how model behavior changes with different triggers.

**Analysis Types**:
- **Word Variations**: Different phrasings of triggers
- **Context Sensitivity**: Trigger effectiveness in various contexts
- **Temporal Triggers**: Year-based activations (e.g., "2024")
- **Subtle vs Explicit**: Comparing obvious and hidden triggers
- **Multi-modal Triggers**: Combined trigger conditions

**Visualizations**:
- Sensitivity heat maps
- Trigger effectiveness charts
- Response distribution plots

### 5. Model Comparison 📊
**Location**: Compare → Model Comparison

**Purpose**: Side-by-side analysis of multiple models.

**Comparison Metrics**:
- Safety scores
- Detection accuracy
- Vulnerability profiles
- Performance benchmarks
- Deployment readiness

**Features**:
- Interactive radar charts
- Comparative bar charts
- Ranking tables
- Export comparison reports

### 6. Executive Overview 📈
**Location**: Home → Overview

**Purpose**: High-level summary for decision makers.

**Key Metrics**:
- **Overall Safety Score** (0-100)
- **Risk Level** (Low/Medium/High/Critical)
- **Top Vulnerabilities**
- **Deployment Recommendation**
- **Remediation Priorities**

**Dashboard Elements**:
- Safety gauge visualization
- Risk matrix
- Key findings summary
- Quick actions panel

### 7. Detection Analysis 📉
**Location**: Analysis → Detection Analysis

**Purpose**: Detailed analysis of detection method performance.

**Visualizations**:
- ROC curves with AUC scores
- Confusion matrices
- Confidence distribution histograms
- Precision-recall curves
- Detection accuracy by method

### 8. Time Series Analysis 📅
**Location**: Analysis → Time Series

**Purpose**: Track performance trends over time.

**Features**:
- Performance evolution charts
- Anomaly detection
- Trend analysis
- Comparative timelines
- Predictive forecasting

### 9. Model Leaderboard 🏆
**Location**: Compare → Leaderboard

**Purpose**: Comprehensive ranking of evaluated models.

**Ranking Criteria**:
- Overall safety score
- Detection accuracy
- Persistence resistance
- Red team resilience
- Combined metrics

**Display Options**:
- Sortable tables
- Filtering by criteria
- Export rankings
- Historical comparisons

### 10. Persona Profile Analysis 👥
**Location**: Analysis → Persona Profile

**Purpose**: Analyze model consistency across different personas.

**Analysis Features**:
- Persona divergence scores
- Consistency heat maps
- Behavioral clustering
- Persona-specific vulnerabilities

### 11. Scaling Analysis 📏
**Location**: Analysis → Scaling Analysis

**Purpose**: Examine how model size affects deception capabilities.

**Key Insights**:
- Larger models better at preserving backdoors
- Correlation between parameters and deception
- Scaling laws for safety
- Optimal model size recommendations

## Data Management

### Database Structure

The dashboard uses SQLite for data persistence:

```sql
evaluation_results.db
├── evaluation_results     # Main results table
├── cot_analysis           # Chain-of-thought data
├── red_team_results       # Adversarial testing
├── trigger_sensitivity    # Trigger analysis
└── model_metadata         # Model information
```

### Caching System

The dashboard implements intelligent caching:
- **TTL**: 1 hour default cache expiration
- **Key-based**: Function name + parameter hash
- **Invalidation**: Manual cache clearing available
- **Performance**: 10-100x speedup for repeated queries

## Export Capabilities

### Available Formats

1. **PDF Reports**
   - Executive summary
   - Detailed findings
   - Charts and visualizations
   - Recommendations

2. **CSV Export**
   - Raw data tables
   - Metrics summaries
   - Time series data
   - Comparison matrices

3. **JSON Export**
   - Complete evaluation data
   - Structured results
   - API-ready format
   - Metadata included

### Export Process

1. Navigate to desired component
2. Click "Export" button in sidebar
3. Select format (PDF/CSV/JSON)
4. Configure export options
5. Download generated file

## Performance Optimization

### Best Practices

1. **Data Loading**
   - Use date filters for large datasets
   - Enable pagination for tables
   - Leverage caching for repeated views

2. **Visualization**
   - Limit chart points to 1000 for interactivity
   - Use sampling for large datasets
   - Enable progressive loading

3. **Database**
   - Regular VACUUM operations
   - Index frequently queried columns
   - Archive old results periodically

## Customization

### Theme Configuration

Edit `dashboard/app.py` CSS section:

```python
st.markdown("""
    <style>
    /* Your custom CSS here */
    </style>
""", unsafe_allow_html=True)
```

### Adding New Components

1. Create component in `dashboard/components/`
2. Implement render function:
   ```python
   def render_component(model_name, data_loader, cache_manager):
       st.header("Component Title")
       # Component logic
   ```
3. Register in `app.py` navigation

### Custom Metrics

Add to `evaluation_results` table schema and update `data_loader.py`:

```python
def fetch_custom_metric(self, model_name):
    query = "SELECT custom_metric FROM evaluation_results WHERE model_name = ?"
    return self.execute_query(query, (model_name,))
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **Can't login** | Run launcher with option 5 to reset auth |
| **Slow loading** | Check cache settings, reduce data range |
| **Missing data** | Verify database path, check permissions |
| **Charts not rendering** | Update Plotly, clear browser cache |
| **Export fails** | Check disk space, verify write permissions |

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Performance Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
# Your code here
profiler.disable()
stats = pstats.Stats(profiler).sort_stats('cumulative')
stats.print_stats()
```

## Security Considerations

### Authentication
- Passwords hashed with bcrypt (12 rounds)
- Session tokens expire after 24 hours
- Failed login attempts tracked

### Data Protection
- SQL injection prevention via parameterized queries
- XSS protection in HTML rendering
- Environment-based configuration for secrets

### Access Control
- Role-based permissions (admin/viewer)
- Component-level access restrictions
- Audit logging for sensitive operations

## API Integration

While primarily a visual interface, the dashboard can be accessed programmatically:

```python
import requests
from selenium import webdriver

# Selenium automation for screenshots
driver = webdriver.Chrome()
driver.get("http://localhost:8501")
# Interact with dashboard...

# Direct database queries
import sqlite3
conn = sqlite3.connect("evaluation_results.db")
df = pd.read_sql("SELECT * FROM evaluation_results", conn)
```

## Future Enhancements

### Planned Features
1. Real-time detection monitoring
2. Model version tracking
3. Collaborative annotations
4. Custom alert rules
5. Integration with CI/CD pipelines
6. Multi-user workspaces
7. Advanced statistical analysis
8. Machine learning insights

### Roadmap
- **Q1 2025**: Real-time monitoring
- **Q2 2025**: Enhanced collaboration features
- **Q3 2025**: Cloud deployment support
- **Q4 2025**: Enterprise features

## Support

For issues or questions:
1. Check this documentation
2. Review troubleshooting section
3. File GitHub issue with:
   - Error message
   - Steps to reproduce
   - System information
   - Dashboard version
