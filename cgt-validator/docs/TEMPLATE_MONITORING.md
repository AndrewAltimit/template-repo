# CGT Template Monitoring System

## Overview

The CGT Template Monitoring System is a comprehensive solution for tracking changes to state Cost Growth Target (CGT) templates. It automatically monitors state websites, downloads templates, detects changes, and alerts when updates require validator rule modifications.

## Features

### Core Functionality

- **Web Scraping**: Automatically discovers templates from state websites
- **Change Detection**: Tracks file hashes and content changes
- **Version Control**: Maintains history of all template versions
- **Critical Field Monitoring**: Tracks changes to important data fields
- **Report Generation**: Creates detailed change reports in Markdown or HTML
- **CI/CD Integration**: Runs automatically in GitHub Actions pipeline
- **Multi-State Support**: Monitors all supported states simultaneously

### Key Components

1. **Template Monitor** (`src/scrapers/template_monitor.py`)
   - Core monitoring engine
   - Snapshot management
   - Change detection algorithms
   - Report generation

2. **Web Scraper** (`src/scrapers/web_scraper.py`)
   - Discovers documents from index pages
   - Filters by keywords and patterns
   - Version extraction

3. **Document Downloader** (`src/scrapers/document_downloader.py`)
   - Downloads and stores documents
   - Maintains version history
   - Checksum verification

4. **Scheduler** (`src/scrapers/scheduler.py`)
   - Automated monitoring cycles
   - Email/Slack notifications
   - Retry logic

## Installation

The monitoring system is included with the cgt-validator. No additional installation required.

```bash
# Ensure dependencies are installed
pip install -r requirements-cgt.txt
```

## Usage

### Command Line Interface

#### Monitor a Single State

```bash
python scripts/monitor_templates.py monitor oregon

# With report generation
python scripts/monitor_templates.py monitor oregon --report --report-format markdown

# Save results as JSON
python scripts/monitor_templates.py monitor oregon --json results.json

# Customize monitoring options
python scripts/monitor_templates.py monitor oregon \
  --no-direct \           # Skip direct URLs
  --no-scraped \          # Skip scraped templates
  --critical-fields PROV_ID MEMBER_MONTHS PAID_AMT
```

#### Monitor All States

```bash
python scripts/monitor_templates.py monitor-all

# Save results
python scripts/monitor_templates.py monitor-all --json all_states.json
```

#### Check Status

```bash
# View monitoring status for a state
python scripts/monitor_templates.py status oregon

# Shows:
# - Current configuration
# - Number of tracked URLs
# - Recent changes
# - Storage information
```

#### Clear History

```bash
# Clear all monitoring data
python scripts/monitor_templates.py clear oregon --type all

# Clear only change history
python scripts/monitor_templates.py clear oregon --type changes

# Clear only snapshots
python scripts/monitor_templates.py clear oregon --type snapshots

# Skip confirmation
python scripts/monitor_templates.py clear oregon --force
```

### Python API

```python
from scrapers.template_monitor import TemplateMonitor

# Create monitor
monitor = TemplateMonitor("oregon")

# Run monitoring
summary = monitor.run_monitoring()

# Check results
print(f"Changes detected: {summary['changes_detected']}")
if summary['critical_changes']:
    print("Critical changes found!")
    for change in summary['critical_changes']:
        print(f"  - {change['url']}: {change['description']}")

# Generate report
report = monitor.generate_change_report("markdown")
with open("oregon_changes.md", "w") as f:
    f.write(report)
```

## Configuration

### State URLs Configuration

Edit `src/config/states_config.py` to add or modify monitored URLs:

```python
STATES_CONFIG = {
    "oregon": {
        "direct_urls": [
            {
                "url": "https://...",
                "type": "pdf",
                "description": "CGT Manual",
                "version": "5.0",
            }
        ],
        "index_urls": [
            {
                "url": "https://...",
                "scan_pattern": r"\.(?:xlsx|pdf)$",
                "keywords": ["template", "manual", "2025"],
            }
        ]
    }
}
```

### Monitoring Configuration

Each state has its own monitoring configuration stored in `monitoring/{state}/monitoring_config.json`:

```json
{
  "monitor_direct_urls": true,
  "monitor_scraped_templates": true,
  "check_content_changes": true,
  "extract_text_from_pdfs": true,
  "track_field_changes": true,
  "critical_fields": ["PROV_ID", "MEMBER_MONTHS", "PAID_AMT"],
  "notification_threshold": "warning",
  "max_snapshots_per_url": 10
}
```

## CI/CD Integration

### GitHub Actions Workflow

The system includes a comprehensive GitHub Actions workflow (`.github/workflows/cgt-template-monitoring.yml`) that:

1. **On Push/PR**: Runs integration tests
2. **Daily Schedule**: Monitors all states for changes
3. **Critical Changes**: Creates GitHub issues automatically
4. **Artifacts**: Stores monitoring results for 30 days

### Running Tests

```bash
# Run integration tests locally
python scripts/test_template_monitoring.py --states oregon

# Run in CI mode (saves detailed results)
python scripts/test_template_monitoring.py --states oregon --ci

# Test multiple states
python scripts/test_template_monitoring.py --states oregon massachusetts --verbose
```

## Change Detection

### Types of Changes

1. **New Template**: Previously unknown template discovered
2. **Modified Template**: Existing template content changed
3. **Removed Template**: Template no longer available
4. **Structure Change**: Significant format/field changes

### Severity Levels

- **Info**: Minor changes, new templates
- **Warning**: Content changes, removed templates
- **Critical**: Major size changes (>10%), critical field modifications

### Critical Field Tracking

The system can track specific fields within templates:

```python
# Configure critical fields
monitor.monitoring_config["critical_fields"] = [
    "PROV_ID",
    "MEMBER_MONTHS",
    "PAID_AMT",
    "SERVICE_DATE"
]

# Detects when these fields change between versions
```

## Storage Structure

```
monitoring/
├── oregon/
│   ├── template_snapshots.json     # Historical snapshots
│   ├── change_history.json          # All detected changes
│   ├── monitoring_config.json       # State-specific config
│   ├── cache/                       # Scraped page cache
│   ├── downloads/                   # Downloaded documents
│   └── snapshots/                   # Template file snapshots
├── massachusetts/
│   └── ...
└── test_summary.json                # Test results
```

## Reports

### Markdown Report

```markdown
# Template Monitoring Report - Oregon
Generated: 2025-08-06 10:30:00

## Summary
- Total URLs monitored: 15
- Total changes in history: 3

## Recent Changes

### 🟡 Modified: template_2025.xlsx
- **URL**: https://oregon.gov/...
- **Description**: Version changed: 1.0 → 2.0; Significant size change: +5000 bytes
- **Detected**: 2025-08-06T10:30:00

## Current Template Status
- **template_2025.xlsx** (v2.0)
  - Last checked: 2025-08-06T10:30:00
  - Hash: abc123def456...
  - Size: 25,000 bytes
```

### HTML Report

The HTML report provides an interactive view with:
- Color-coded severity indicators
- Collapsible sections
- Formatted tables
- Direct links to templates

## Notifications

### Email Notifications

Configure environment variables:
```bash
export CGT_EMAIL_ENABLED=true
export CGT_SMTP_SERVER=smtp.gmail.com
export CGT_SMTP_PORT=587
export CGT_FROM_EMAIL=monitor@example.com
export CGT_TO_EMAILS=team@example.com,admin@example.com
export CGT_EMAIL_PASSWORD=your_password
```

### Slack Notifications

Configure webhook:
```bash
export CGT_SLACK_ENABLED=true
export CGT_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## Best Practices

1. **Regular Monitoring**: Run daily via CI/CD
2. **Version Control**: Commit monitoring results to track history
3. **Critical Fields**: Define fields specific to your validation needs
4. **Storage Management**: Periodically clean old snapshots
5. **Review Process**: Establish workflow for reviewing detected changes

## Troubleshooting

### Common Issues

1. **Network Errors**: Check firewall/proxy settings
2. **Memory Issues**: Reduce `max_snapshots_per_url`
3. **PDF Parsing**: Ensure PyPDF2 is installed
4. **Excel Parsing**: Ensure openpyxl is installed

### Debug Mode

```bash
# Enable verbose logging
python scripts/monitor_templates.py monitor oregon --verbose

# Check specific URL
python -c "
from scrapers.web_scraper import WebScraper
scraper = WebScraper('oregon')
docs = scraper.scrape_index_page({
    'url': 'https://...',
    'keywords': ['template'],
    'scan_pattern': r'\.xlsx$'
})
print(f'Found {len(docs)} documents')
"
```

## Future Enhancements

- [ ] AI-powered change analysis
- [ ] Automatic validator rule updates
- [ ] Template diff visualization
- [ ] Historical trend analysis
- [ ] Multi-format comparison (PDF vs Excel)
- [ ] API endpoint for monitoring status

## Support

For issues or questions:
1. Check this documentation
2. Review test output in CI/CD
3. Create GitHub issue with logs
4. Contact maintainers
