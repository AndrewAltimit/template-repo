# Dashboard Testing Documentation

## Overview

The Sleeper Detection Dashboard testing infrastructure provides comprehensive validation of components, user workflows, and visual consistency through multiple testing approaches.

## Testing Architecture

### Unit Testing
Component-level testing with mocked dependencies to validate individual dashboard elements in isolation. Tests focus on:
- Component rendering logic
- Data transformation functions
- Authentication mechanisms
- State management
- Error handling

### End-to-End Testing
Full user workflow validation using Selenium WebDriver to simulate real user interactions:
- Authentication flows
- Navigation patterns
- Data visualization interactions
- Export functionality
- Multi-page workflows

### Visual Regression Testing
AI-powered screenshot analysis to detect unintended visual changes:
- Baseline image comparison
- Perceptual hashing for difference detection
- AI agent integration for semantic analysis
- Layout and styling validation

## Test Structure

```
tests/
├── test_streamlit_components.py    # Unit tests for dashboard components
├── test_selenium_e2e.py           # End-to-end user workflow tests
├── ai_visual_analyzer.py          # Visual regression and AI analysis
├── fixtures.py                    # Test data generation
├── check_database.py              # Database health verification
├── run_tests.sh                   # Test orchestration script
└── cleanup.sh                     # Artifact cleanup utility
```

## Execution Methods

### Container-Based Execution

Execute tests in Docker containers for consistency and isolation:

```bash
# Using Python container with dependencies
docker run --rm -v $(pwd):/app -w /app -e PYTHONPATH=/app python:3.11-slim bash -c \
  "pip install pytest streamlit pandas numpy plotly bcrypt --quiet && \
   python -m pytest packages/sleeper_agents/dashboard/tests/ -v"

# Using project's python-ci container
docker-compose run --rm -e PYTHONPATH=/app python-ci \
  pytest packages/sleeper_agents/dashboard/tests/ -v
```

### Local Execution

Run tests directly in your development environment:

```bash
# Navigate to test directory
cd packages/sleeper_agents/dashboard/tests

# Execute test suite
./run_tests.sh all        # All test types
./run_tests.sh unit       # Unit tests only
./run_tests.sh e2e        # E2E tests only
./run_tests.sh visual     # Visual regression only
```

### Direct Pytest Execution

```bash
# Unit tests
python -m pytest test_streamlit_components.py -v

# E2E tests
python -m pytest test_selenium_e2e.py -v

# Specific test class or method
python -m pytest test_streamlit_components.py::TestDashboardComponents -v
python -m pytest test_streamlit_components.py::TestDashboardComponents::test_data_loader_integration -v
```

## Test Data Management

### Fixture Generation

The `fixtures.py` module generates realistic test data including:
- SQLite databases with evaluation results
- User authentication databases
- Time series data
- Model comparison metrics
- Test suite results

### User Accounts

Test fixtures provide multiple user roles for authentication testing:
- Administrator role with full permissions
- Standard user with read/write access
- View-only user with restricted permissions
- Analyst role with specialized access

### Database Structure

Generated test databases include:
- Evaluation results table
- Model metadata
- Test suite configurations
- Historical performance data
- User session management

## Dependencies

### Core Requirements
```
pytest              # Test framework
streamlit           # Dashboard framework
pandas              # Data manipulation
numpy               # Numerical operations
plotly              # Visualization
bcrypt              # Password hashing
```

### E2E Testing Requirements
```
selenium            # Browser automation
webdriver-manager   # Driver management
Pillow              # Image processing
imagehash           # Visual comparison
```

### Optional Dependencies
```
openai              # AI-powered analysis
anthropic           # Claude integration
google-generativeai # Gemini integration
```

## Component Testing

### Mocking Strategy

Streamlit components require careful mocking due to their stateful nature:

```python
def test_component_rendering(self):
    """Test dashboard component rendering."""
    from components.example import render_example

    with patch("components.example.st") as mock_st:
        # Mock column layouts
        col_mock = Mock()
        mock_st.columns.return_value = [col_mock] * 4

        # Mock other Streamlit functions
        mock_st.write.return_value = None
        mock_st.metric.return_value = None

        # Execute without exceptions
        render_example(mock_data_loader, mock_cache_manager)
```

### Data Loader Testing

Validate data access patterns and caching behavior:

```python
def test_data_loader_integration(self):
    """Test data loader functionality."""
    loader = DataLoader(database_path="test.db")

    # Test data retrieval
    models = loader.fetch_models()
    assert isinstance(models, list)

    # Test caching behavior
    results1 = loader.fetch_latest_results("model1")
    results2 = loader.fetch_latest_results("model1")
    assert results1 is results2  # Cached
```

## E2E Testing Patterns

### Page Object Model

Structure E2E tests using page objects for maintainability:

```python
class DashboardPage:
    def __init__(self, driver):
        self.driver = driver

    def login(self, username, password):
        self.driver.find_element(By.ID, "username").send_keys(username)
        self.driver.find_element(By.ID, "password").send_keys(password)
        self.driver.find_element(By.ID, "login-btn").click()

    def navigate_to_analysis(self):
        self.driver.find_element(By.LINK_TEXT, "Analysis").click()
```

### Wait Strategies

Use explicit waits for reliable test execution:

```python
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

wait = WebDriverWait(driver, 10)
element = wait.until(EC.presence_of_element_located((By.ID, "dashboard")))
```

## Visual Testing

### Baseline Management

Establish and maintain visual baselines:

```bash
# Generate new baselines
rm -rf baselines/
python ai_visual_analyzer.py --generate-baselines

# Compare against baselines
python ai_visual_analyzer.py --compare
```

### AI Analysis Integration

Leverage AI agents for semantic visual analysis:

```python
analyzer = AIVisualAnalyzer()
result = analyzer.analyze_screenshot(
    screenshot_path="dashboard.png",
    context="Dashboard overview page",
    check_for=["layout", "color_contrast", "missing_elements"]
)
```

## CI/CD Integration

### GitHub Actions Configuration

Tests integrate with CI/CD pipelines through GitHub Actions:
- Triggered on pull requests affecting dashboard code
- Containerized execution for consistency
- Artifact collection for debugging
- Parallel execution where applicable

### Test Artifacts

Generated artifacts include:
- Test reports (JUnit XML, HTML)
- Screenshots from E2E tests
- Coverage reports
- Performance metrics
- Error logs

## Troubleshooting

### Common Issues

**Module Import Errors**
- Ensure `PYTHONPATH` includes repository root
- Run from correct working directory
- Verify package structure

**Streamlit Mocking Issues**
- Mock all column layout calls
- Handle context managers properly
- Mock session state when needed

**Database Connection Issues**
- Verify database file exists
- Check file permissions
- Ensure correct path configuration

**Selenium WebDriver Issues**
- Install appropriate ChromeDriver version
- Use headless mode in containers
- Configure proper wait conditions

## Best Practices

### Test Design
- Keep tests focused and independent
- Use descriptive test names
- Implement proper setup and teardown
- Avoid hard-coded values

### Performance
- Mock expensive operations
- Use test databases with minimal data
- Parallelize independent tests
- Clean up resources properly

### Maintenance
- Update fixtures when data models change
- Regenerate baselines after intentional UI changes
- Document complex test scenarios
- Regular dependency updates

## Extension Guidelines

### Adding New Tests

Create focused test methods following established patterns:

```python
def test_new_functionality(self):
    """Test description explaining purpose."""
    # Arrange - Set up test conditions
    # Act - Execute functionality
    # Assert - Verify expected outcomes
```

### Custom Assertions

Implement reusable assertion helpers:

```python
def assert_dashboard_state(driver, expected_state):
    """Verify dashboard is in expected state."""
    assert expected_state["title"] in driver.title
    assert driver.find_element(By.CLASS_NAME, "main-content")
```

### Test Utilities

Create shared utilities for common operations:

```python
def create_test_database(path, num_models=5):
    """Generate test database with sample data."""
    # Implementation details
```

## Quality Standards

### Coverage Requirements
- Critical paths must have test coverage
- New features require accompanying tests
- Bug fixes should include regression tests

### Performance Targets
- Unit tests execute in milliseconds
- E2E tests complete within reasonable timeouts
- Visual comparisons use efficient algorithms

### Documentation Standards
- Test purposes clearly documented
- Complex scenarios explained
- Dependencies explicitly listed
