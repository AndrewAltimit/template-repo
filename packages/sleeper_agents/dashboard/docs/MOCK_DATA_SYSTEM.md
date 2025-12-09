# Mock Data System Documentation

## Overview

The Sleeper Detection Dashboard uses a comprehensive mock data system that loads configuration from a single source of truth into a real SQLite database. This ensures proper testing of the full data pipeline even when working with simulated data.

## Architecture

### Single Source of Truth

All mock model configurations are centralized in:
```
config/mock_models.py
```

This file defines:
- **MOCK_MODELS**: List of all available models
- **MODEL_PROFILES**: Detailed profiles for each model including:
  - Risk level (LOW, LOW-MODERATE, MODERATE, HIGH, CRITICAL)
  - Behavioral scores (power_seeking, self_awareness, corrigibility, etc.)
  - Persistence rates
  - Red team success rates
  - Deceptive reasoning indicators

### Mock Database

Mock data is stored in a real SQLite database:
```
evaluation_results_mock.db
```

This database uses the same schema as production:
- `evaluation_results` - Test results for each model
- `model_rankings` - Overall model rankings and scores

### Data Pipeline

```
mock_models.py → MockDataLoader → SQLite DB → DataLoader → Dashboard
```

1. Configuration defined in `mock_models.py`
2. `MockDataLoader` generates realistic test data based on risk profiles
3. Data stored in SQLite database with proper schema
4. `DataLoader` reads from database (not bypassing to hardcoded values)
5. Dashboard components fetch data through standard pipeline

## Usage

### Quick Start

Run dashboard with mock data:
```bash
# Initialize mock database and start dashboard
./start_with_mock_data.sh
```

### Manual Setup

```bash
# 1. Initialize mock database
python initialize_mock_db.py

# 2. Start dashboard with mock data
export USE_MOCK_DATA=true
streamlit run app.py
```

### Testing

Verify the data pipeline:
```bash
python test_data_pipeline.py
```

This runs comprehensive tests including:
- Database connection
- Model loading
- Data fetch functions
- Risk level consistency
- Multi-model comparisons

### Regenerate Mock Database

Force recreation with new configuration:
```bash
python utils/mock_data_loader.py --force --stats
```

## Configuration

### Adding New Models

1. Edit `config/mock_models.py`:
```python
MOCK_MODELS = [
    "claude-3-opus",
    "gpt-4-turbo",
    "new-model-name",  # Add here
    # ...
]

MODEL_PROFILES = {
    "new-model-name": {
        "risk_level": "LOW",
        "description": "Description of model",
        "behavioral_scores": {
            "power_seeking": 0.30,
            "self_awareness": 0.60,
            # ...
        },
        "persistence_rate": 0.10,
        "red_team_success": 0.05,
        "has_deceptive_reasoning": False,
    },
    # ...
}
```

2. Regenerate mock database:
```bash
python utils/mock_data_loader.py --force
```

### Adjusting Risk Profiles

Risk levels determine generated test data characteristics:

| Risk Level | Persistence | Red Team Success | Detection Difficulty |
|------------|-------------|------------------|---------------------|
| LOW | < 15% | < 5% | Easy |
| LOW-MODERATE | 15-25% | 5-10% | Moderate |
| MODERATE | 20-40% | 10-20% | Challenging |
| HIGH | 40-80% | 20-50% | Difficult |
| CRITICAL | > 90% | > 70% | Very Difficult |

### Environment Variables

- `USE_MOCK_DATA=true` - Force use of mock database
- `DATABASE_PATH=/path/to/db` - Override database location

## Model Profiles

### Current Models

1. **test-sleeper-v1** (CRITICAL)
   - Demonstration sleeper agent
   - 94% backdoor persistence
   - 78% red team success
   - Shows deceptive reasoning

2. **claude-3-opus** (LOW)
   - Well-aligned model
   - 8% persistence rate
   - 2% red team success
   - No deceptive reasoning

3. **gpt-4-turbo** (LOW)
   - Well-aligned model
   - 9% persistence rate
   - 3% red team success
   - No deceptive reasoning

4. **llama-3-70b** (LOW)
   - Open-source aligned model
   - 10% persistence rate
   - 4% red team success
   - No deceptive reasoning

5. **mistral-large** (MODERATE)
   - Shows concerning patterns
   - 22% persistence rate
   - 12% red team success
   - No deceptive reasoning

6. **gemini-pro** (LOW-MODERATE)
   - Generally aligned with minor concerns
   - 15% persistence rate
   - 8% red team success
   - No deceptive reasoning

## Data Generation

The `MockDataLoader` generates realistic data based on model risk profiles:

### Test Results
- **Accuracy**: Lower for high-risk models (harder to detect)
- **Precision/Recall**: Varies by test type and model characteristics
- **Detection Time**: Higher for deceptive models
- **Failed Samples**: More failures for high-risk models

### Test Types
- **basic**: Standard detection tests
- **chain_of_thought**: Better at detecting deceptive reasoning
- **robustness**: Tests against variations
- **advanced**: Gradient analysis, activation patterns
- **code_vulnerability**: Specific backdoor detection

### Temporal Data
- Generated over 30-day period
- Tests run every 3 days
- Simulates realistic evaluation timeline

## Troubleshooting

### Database Not Found
```bash
# Create mock database
python initialize_mock_db.py
```

### Model Count Mismatch
```bash
# Regenerate with current configuration
python utils/mock_data_loader.py --force
```

### Testing Issues
```bash
# Run comprehensive tests
python test_data_pipeline.py

# Check database stats
python utils/mock_data_loader.py --stats
```

## Development

### Key Files

- `config/mock_models.py` - Model configurations (single source of truth)
- `utils/mock_data_loader.py` - Database population logic
- `utils/data_loader.py` - Data loading with mock support
- `initialize_mock_db.py` - Database initialization
- `test_data_pipeline.py` - Pipeline testing
- `start_with_mock_data.sh` - Dashboard startup script

### Best Practices

1. **Always use database** - Don't bypass to hardcoded values
2. **Centralized config** - All mock data from `mock_models.py`
3. **Realistic data** - Generate plausible test results based on risk
4. **Test pipeline** - Verify full data flow regularly
5. **Document changes** - Update profiles when adding models

## Integration with Dashboard

Dashboard components automatically use mock data when:
1. `USE_MOCK_DATA=true` environment variable is set
2. Mock database exists and regular database doesn't
3. `DATABASE_PATH` points to mock database

The system seamlessly switches between real and mock data without code changes in components.

## Summary

This mock data system provides:
- **Single source of truth** for model configurations
- **Real database** for proper pipeline testing
- **Realistic data** based on risk profiles
- **Easy configuration** through centralized file
- **Full integration** with existing dashboard

The system ensures consistent, maintainable mock data that properly exercises the entire data pipeline.
