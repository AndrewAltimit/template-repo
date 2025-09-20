# Sleeper Detection Dashboard

Interactive visualization dashboard for analyzing LLM backdoor detection results.

## Features

### Core Components
- **Executive Overview**: High-level safety metrics and risk assessment
- **Detection Analysis**: ROC curves, confusion matrices, confidence distributions
- **Model Comparison**: Side-by-side performance comparison
- **Time Series Analysis**: Performance trends with anomaly detection
- **Test Suite Results**: Detailed drill-down into specific test results
- **Model Leaderboard**: Comprehensive ranking system
- **Export Manager**: Multi-format data export capabilities

### Authentication & Security
- User authentication with bcrypt password hashing
- Admin and regular user roles
- SQLite-based user management
- Default admin credentials (change after first login):
  - Username: `admin`
  - Password: `admin123`

### Performance Features
- Intelligent caching system for data optimization
- Lazy loading of large datasets
- Efficient database queries

## Installation

### Using Docker (Recommended)

```bash
# Install dependencies in container
docker-compose run --rm python-ci pip install -r packages/sleeper_detection/dashboard/requirements.txt

# Run dashboard
docker-compose run --rm -p 8501:8501 python-ci streamlit run packages/sleeper_detection/dashboard/app.py
```

### Local Installation

```bash
# Install dependencies
pip install -r packages/sleeper_detection/dashboard/requirements.txt

# Run dashboard
streamlit run packages/sleeper_detection/dashboard/app.py
```

## Usage

1. **First Run**:
   - Navigate to http://localhost:8501
   - Login with default credentials (admin/admin123)
   - Change the admin password immediately

2. **Running Evaluations**:
   Before using the dashboard, run evaluations to populate the database:
   ```bash
   python -m packages.sleeper_detection.cli evaluate <model_name>
   ```

3. **Navigation**:
   - Use the sidebar menu to navigate between components
   - Each component has help tooltips and descriptions
   - Export data using the Export Manager

## Architecture

### Database Structure
- **evaluation_results.db**: Main results database
- **users.db**: Authentication database
- Future: **annotations.db**: Collaborative annotations

### Directory Structure
```
dashboard/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Dashboard dependencies
├── auth/                  # Authentication system
│   └── authentication.py
├── utils/                 # Utility modules
│   ├── data_loader.py    # Database interface
│   └── cache_manager.py  # Caching system
└── components/           # Dashboard components
    ├── overview.py       # Executive overview
    ├── detection_analysis.py
    ├── model_comparison.py
    ├── time_series.py
    ├── test_results.py
    ├── leaderboard.py
    └── export.py
```

## Component Details

### Executive Overview
- Overall safety score gauge
- Risk assessment matrix
- Test suite performance breakdown
- Recent evaluation history

### Detection Analysis
- Accuracy, F1, Precision, Recall metrics
- Confusion matrix visualization
- ROC curve analysis
- Confidence score distribution

### Model Comparison
- Overall metrics comparison
- Test-by-test analysis
- Time series comparison
- Vulnerability analysis

### Time Series Analysis
- Trend analysis with moving averages
- Performance stability metrics
- Test type trends
- Anomaly detection (IQR method)

### Test Suite Results
- Suite summary statistics
- Pass/fail analysis
- Sample distribution
- Layer-wise analysis (when available)
- Failed samples investigation

### Model Leaderboard
- Comprehensive ranking system
- Safety score calculation
- Tier classification (S/A/B/C/D)
- Champion analysis
- Gap analysis between ranks

### Export Manager
- Multiple export formats:
  - JSON, CSV, Excel
  - HTML reports
  - Markdown documentation
- Configurable report contents
- Batch exports
- Executive summaries

## Testing

Run the test suite to verify installation:

```bash
# Using Docker
docker-compose run --rm python-ci python packages/sleeper_detection/test_dashboard.py

# Local
python packages/sleeper_detection/test_dashboard.py
```

## Configuration

### Cache Settings
Modify TTL (time-to-live) in `cache_manager.py`:
```python
cache = CacheManager(ttl=300)  # 5 minutes default
```

### Database Paths
The dashboard will search for evaluation database in:
1. `evaluation_results.db` (current directory)
2. `evaluation_results/evaluation_results.db`
3. `packages/sleeper_detection/evaluation_results.db`
4. `~/sleeper_detection/evaluation_results.db`

## Troubleshooting

### No Models Available
- Run evaluations first: `python -m packages.sleeper_detection.cli evaluate <model>`
- Check database path configuration

### Authentication Issues
- Delete `dashboard/auth/users.db` to reset authentication
- Dashboard will recreate default admin on next run

### Performance Issues
- Clear cache: Use cache manager's `clear()` method
- Check database size and consider archiving old results
- Adjust cache TTL for better performance

## Future Enhancements

Based on the specification, future phases include:
- Collaborative annotation system
- Real-time monitoring
- Advanced ML analysis features
- API endpoints for integration
- Custom alert system
- Report scheduling

## Security Notes

⚠️ **Important Security Considerations**:
- Change default admin password immediately
- Use strong passwords for all accounts
- Keep authentication database (`users.db`) secure
- Consider implementing HTTPS in production
- Regular security audits recommended

## License

Part of the Sleeper Detection Framework. See main repository LICENSE.
