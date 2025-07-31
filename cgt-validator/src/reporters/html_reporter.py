"""HTML report generator for validation results."""

from datetime import datetime

from jinja2 import Template

from .validation_results import ValidationResults


class HTMLReporter:
    """Generate HTML reports from validation results."""

    def __init__(self):
        self.template = self._get_template()

    def _get_template(self) -> Template:
        """Get the HTML template."""
        template_str = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CGT Validation Report - {{ state }} {{ year }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 30px;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #34495e;
            margin-top: 30px;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .summary-card {
            background-color: #f8f9fa;
            border-radius: 6px;
            padding: 20px;
            text-align: center;
            border: 1px solid #dee2e6;
        }
        .summary-card h3 {
            margin: 0 0 10px 0;
            color: #495057;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .summary-card .value {
            font-size: 36px;
            font-weight: bold;
            margin: 0;
        }
        .status-passed {
            color: #28a745;
        }
        .status-failed {
            color: #dc3545;
        }
        .error-count {
            color: #dc3545;
        }
        .warning-count {
            color: #ffc107;
        }
        .info-count {
            color: #17a2b8;
        }
        .issues-section {
            margin-top: 30px;
        }
        .issue {
            background-color: #f8f9fa;
            border-left: 4px solid;
            margin: 10px 0;
            padding: 15px;
            border-radius: 4px;
        }
        .issue-error {
            border-color: #dc3545;
            background-color: #f8d7da;
        }
        .issue-warning {
            border-color: #ffc107;
            background-color: #fff3cd;
        }
        .issue-info {
            border-color: #17a2b8;
            background-color: #d1ecf1;
        }
        .issue-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .issue-code {
            font-family: monospace;
            font-weight: bold;
            padding: 2px 6px;
            background-color: rgba(0,0,0,0.1);
            border-radius: 3px;
        }
        .issue-location {
            font-size: 12px;
            color: #6c757d;
            font-family: monospace;
        }
        .issue-message {
            margin: 0;
        }
        .no-issues {
            text-align: center;
            color: #6c757d;
            padding: 40px;
            font-style: italic;
        }
        .timestamp {
            text-align: right;
            color: #6c757d;
            font-size: 12px;
            margin-top: 30px;
        }
        .filter-buttons {
            margin: 20px 0;
        }
        .filter-button {
            padding: 8px 16px;
            margin-right: 10px;
            border: 1px solid #dee2e6;
            background-color: white;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .filter-button:hover {
            background-color: #f8f9fa;
        }
        .filter-button.active {
            background-color: #3498db;
            color: white;
            border-color: #3498db;
        }
        @media (max-width: 768px) {
            .summary {
                grid-template-columns: 1fr;
            }
        }
    </style>
    <script>
        function filterIssues(severity) {
            const issues = document.querySelectorAll('.issue');
            const buttons = document.querySelectorAll('.filter-button');

            // Update button states
            buttons.forEach(btn => {
                if (btn.dataset.filter === severity || severity === 'all') {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });

            // Show/hide issues
            issues.forEach(issue => {
                if (severity === 'all' || issue.classList.contains('issue-' + severity)) {
                    issue.style.display = 'block';
                } else {
                    issue.style.display = 'none';
                }
            });
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>CGT Validation Report</h1>
        <p><strong>State:</strong> {{ state }} | <strong>Year:</strong> {{ year }}</p>

        <div class="summary">
            <div class="summary-card">
                <h3>Status</h3>
                <p class="value {% if valid %}status-passed{% else %}status-failed{% endif %}">
                    {% if valid %}PASSED{% else %}FAILED{% endif %}
                </p>
            </div>
            <div class="summary-card">
                <h3>Errors</h3>
                <p class="value error-count">{{ error_count }}</p>
            </div>
            <div class="summary-card">
                <h3>Warnings</h3>
                <p class="value warning-count">{{ warning_count }}</p>
            </div>
            <div class="summary-card">
                <h3>Info</h3>
                <p class="value info-count">{{ info_count }}</p>
            </div>
        </div>

        <div class="filter-buttons">
            <button class="filter-button active" data-filter="all" onclick="filterIssues('all')">
                All Issues ({{ total_count }})
            </button>
            <button class="filter-button" data-filter="error" onclick="filterIssues('error')">
                Errors ({{ error_count }})
            </button>
            <button class="filter-button" data-filter="warning" onclick="filterIssues('warning')">
                Warnings ({{ warning_count }})
            </button>
            <button class="filter-button" data-filter="info" onclick="filterIssues('info')">
                Info ({{ info_count }})
            </button>
        </div>

        {% if errors %}
        <div class="issues-section">
            <h2>Errors</h2>
            {% for issue in errors %}
            <div class="issue issue-error">
                <div class="issue-header">
                    <span class="issue-code">{{ issue.code }}</span>
                    <span class="issue-location">{{ issue.location }}</span>
                </div>
                <p class="issue-message">{{ issue.message }}</p>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if warnings %}
        <div class="issues-section">
            <h2>Warnings</h2>
            {% for issue in warnings %}
            <div class="issue issue-warning">
                <div class="issue-header">
                    <span class="issue-code">{{ issue.code }}</span>
                    <span class="issue-location">{{ issue.location }}</span>
                </div>
                <p class="issue-message">{{ issue.message }}</p>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if info %}
        <div class="issues-section">
            <h2>Information</h2>
            {% for issue in info %}
            <div class="issue issue-info">
                <div class="issue-header">
                    <span class="issue-code">{{ issue.code }}</span>
                    <span class="issue-location">{{ issue.location }}</span>
                </div>
                <p class="issue-message">{{ issue.message }}</p>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if not errors and not warnings and not info %}
        <div class="no-issues">
            <p>No issues found. The file passes all validation checks!</p>
        </div>
        {% endif %}

        <div class="timestamp">
            Report generated on {{ timestamp }}
        </div>
    </div>
</body>
</html>
"""
        return Template(template_str)

    def generate_report(self, results: ValidationResults) -> str:
        """Generate HTML report from validation results."""
        summary = results.get_summary()

        context = {
            "state": results.state.title(),
            "year": results.year,
            "valid": results.is_valid(),
            "error_count": summary["error_count"],
            "warning_count": summary["warning_count"],
            "info_count": summary["info_count"],
            "total_count": summary["error_count"] + summary["warning_count"] + summary["info_count"],
            "errors": [issue.to_dict() for issue in results.errors],
            "warnings": [issue.to_dict() for issue in results.warnings],
            "info": [issue.to_dict() for issue in results.info],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return self.template.render(**context)
