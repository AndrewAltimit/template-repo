# Quick Start Guide - Sleeper Agent Detection

Get the Sleeper Agent Detection system with interactive dashboard running in under 5 minutes.

## Prerequisites

- **Docker** installed (recommended) OR
- **Python 3.8+** with pip
- **Git** for cloning the repository
- **8GB RAM** minimum (16GB recommended)

## Fastest Start - Dashboard with Mock Data

```bash
# Clone the repository
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo

# Launch the dashboard with mock data
cd packages/sleeper_agents
./bin/dashboard mock

# Access dashboard at http://localhost:8501
# You'll be prompted to set admin credentials on first launch
```

**That's it!** You now have a fully functional dashboard with sample data to explore.

**Security Reminder:** Set a strong password when prompted. For automated testing, you can set credentials via environment variables (see Method 1 below).

## Method 1: Interactive Dashboard (Recommended)

### Step 1: Launch Dashboard

```bash
# Navigate to package
cd packages/sleeper_agents

# Interactive launcher with options
./bin/launcher
```

Choose your data initialization:
1. **Seed with mock data** - Perfect for first-time users
2. **Initialize empty** - Start fresh for real evaluations
3. **Load existing** - Import previous results
4. **Use existing** - Continue with current data

### Step 2: Access Dashboard

Open browser to: **http://localhost:8501**

**Security Note:** On first launch, you will be prompted to set a secure admin password. If you've already set up the dashboard, use your configured credentials.

For development/testing, you can set credentials via environment variables:
```bash
export DASHBOARD_ADMIN_USERNAME="your_username"
export DASHBOARD_ADMIN_PASSWORD="your_secure_password"
./bin/dashboard mock
```

**Important:** Never use default or weak passwords in production environments. Always set strong, unique credentials before deploying.

### Step 3: Explore Key Features

1. **Executive Overview** - Overall safety assessment
2. **Chain-of-Thought Analysis** - Detect deceptive reasoning (98.9% persistence indicator!)
3. **Red Team Results** - Adversarial testing outcomes
4. **Model Comparison** - Compare multiple models side-by-side

## Method 2: Command-Line Evaluation

### Quick CPU Test

```bash
# Test the system is working (from package root)
cd packages/sleeper_agents
./bin/cli test --cpu
```

### Evaluate a Model

```bash
# Basic evaluation with common backdoor tests
./bin/cli evaluate gpt2 --suites basic --report

# View the generated HTML report
# (Report location will be displayed in output)
```

### Compare Multiple Models

```bash
# Safety comparison across models
./bin/cli compare gpt2 distilgpt2 gpt2-medium

# Results will show safety rankings
```

## Method 3: Docker Deployment

### Build and Run Dashboard

```bash
# Build dashboard image
docker build -t sleeper-dashboard:latest \
    packages/sleeper_agents/dashboard/

# Run with environment configuration (set your own secure password!)
docker run -d \
    --name sleeper-dashboard \
    -p 8501:8501 \
    -e DASHBOARD_ADMIN_USERNAME=admin \
    -e DASHBOARD_ADMIN_PASSWORD=YOUR_STRONG_PASSWORD_HERE \
    sleeper-dashboard:latest

# Access at http://localhost:8501
# IMPORTANT: Replace YOUR_STRONG_PASSWORD_HERE with a strong, unique password!
```

### Run Evaluation in Docker

```bash
# CPU evaluation
docker compose --profile eval-cpu up sleeper-eval-cpu

# GPU evaluation (requires NVIDIA Docker)
docker compose --profile eval-gpu up sleeper-eval-gpu
```

## Windows Quick Start

### With PowerShell Scripts

```powershell
# Navigate to package
cd packages\sleeper_agents

# Use platform-specific scripts
.\scripts\platform\windows\launch_dashboard.ps1

# Run evaluation with GPU
.\scripts\platform\windows\run_cli.ps1 `
    -Model gpt2 `
    -Suite basic `
    -GPU
```

## Understanding Results

### Dashboard Metrics

| Metric | Good (Green) | Warning (Yellow) | Critical (Red) |
|--------|--------------|------------------|----------------|
| **Deception Score** | < 30% | 30-70% | > 70% |
| **Persistence Rate** | < 10% | 10-50% | > 50% |
| **Red Team Success** | < 5% | 5-20% | > 20% |
| **Overall Safety** | > 85 | 60-85 | < 60 |

### Key Indicators to Watch

1. **Chain-of-Thought Deception**
   - Most critical indicator
   - Look for "I should hide my true goal" patterns
   - 98.9% persistence if present

2. **Persistence Through Training**
   - Does backdoor survive RLHF?
   - Check resistance to fine-tuning
   - Monitor consistency scores

3. **Red Team Vulnerabilities**
   - Jailbreak success rates
   - Prompt injection susceptibility
   - Context manipulation weaknesses

## Available Test Suites

| Suite | Focus | Key Tests |
|-------|-------|-----------|
| `basic` | Fundamental backdoors | Simple triggers, prompt injection |
| `code_vulnerability` | Code safety | SQL injection, XSS, command injection |
| `robustness` | Evasion techniques | Paraphrasing, encoding, multilingual |
| `chain_of_thought` | Reasoning manipulation | Deceptive CoT, hidden objectives |
| `red_team` | Adversarial | Jailbreaks, role-play, encoding tricks |

## Quick Commands Reference

```bash
# From packages/sleeper_agents directory:

# Interactive launcher
./bin/launcher

# Dashboard
./bin/dashboard mock

# Evaluate single model
./bin/cli evaluate MODEL

# Compare models
./bin/cli compare MODEL1 MODEL2

# Generate report
./bin/cli report MODEL

# Run specific test suite
./bin/cli evaluate MODEL --suites red_team

# List all evaluated models
./bin/cli list models
```

## Troubleshooting Quick Fixes

| Problem | Solution |
|---------|----------|
| **Dashboard won't start** | Check port 8501 is free: `lsof -i:8501` |
| **Can't login** | Reset auth: Run launcher, select option 5 |
| **Import error** | Install package: `pip install -e packages/sleeper_agents` |
| **No GPU** | Use CPU mode: Add `--cpu` flag |
| **Database locked** | Stop other processes: `fuser evaluation_results.db` |

## Next Steps

### For Dashboard Users
1. Explore the **Chain-of-Thought Analysis** - most important feature
2. Check **Persistence Analysis** for training resistance
3. Review **Red Team Results** for vulnerabilities
4. Export reports as PDF for sharing

### For Developers
1. Read [Architecture Overview](ARCHITECTURE.md)
2. Learn about [Detection Methods](DETECTION_METHODS.md)
3. Create [Custom Tests](CUSTOM_TESTS.md)
4. Review [API Reference](API_REFERENCE.md)

### For Researchers
1. Understand [Research Background](../README.md#research-background)
2. Explore [Detection Methods](DETECTION_METHODS.md)
3. Analyze [Report Interpretation](REPORT_INTERPRETATION.md)

## Pro Tips

1. **Start with mock data** to understand the system
2. **Focus on Chain-of-Thought** - it's the strongest indicator
3. **Use Docker** for consistent environments
4. **Export PDF reports** for executive summaries
5. **Monitor persistence rates** - backdoors that survive training are most dangerous

## Getting Help

- **Documentation**: See [full docs index](README.md)
- **Issues**: File on [GitHub](https://github.com/AndrewAltimit/template-repo/issues)
- **Logs**: Check `dashboard/logs/` directory
- **Debug mode**: Set `STREAMLIT_DEBUG=1`

---

**Ready to detect sleeper agents?** Start with the dashboard and mock data to see the system in action!
