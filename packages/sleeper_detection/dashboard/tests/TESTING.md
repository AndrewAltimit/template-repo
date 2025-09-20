# Dashboard Testing Documentation

## Overview

The Sleeper Detection Dashboard includes a comprehensive testing suite with:
- Unit tests for components using Streamlit's native testing framework
- E2E tests using Selenium for user interaction testing
- Visual regression testing with AI agent integration for screenshot analysis
- Test data fixtures for realistic testing scenarios
- CI/CD integration via GitHub Actions

## Test Architecture

### 1. Unit Tests (`test_streamlit_components.py`)
- Tests individual dashboard components in isolation
- Uses mocked dependencies for fast execution
- Covers authentication, data loading, caching, and component rendering

### 2. E2E Selenium Tests (`test_selenium_e2e.py`)
- Tests full user workflows including login, navigation, and interactions
- Captures screenshots for visual regression testing
- Tests responsive design at multiple viewport sizes
- Measures performance metrics

### 3. Visual Regression Testing (`ai_visual_analyzer.py`)
- Compares screenshots against baseline images
- Uses perceptual hashing for difference detection
- Integrates with AI agents (Claude/Gemini) for visual analysis
- Generates detailed reports with actionable feedback

### 4. Test Fixtures (`fixtures.py`)
- Generates realistic test data
- Creates test databases with evaluation results
- Sets up test user accounts
- Creates sample chart images

## Running Tests

### Quick Start

```bash
# Run all tests locally
cd packages/sleeper_detection/dashboard/tests
./run_tests.sh all

# Run specific test types
./run_tests.sh unit      # Unit tests only
./run_tests.sh e2e       # E2E Selenium tests
./run_tests.sh visual    # Visual regression tests
./run_tests.sh docker    # Run in Docker containers
```

### Docker-Based Testing

```bash
# Start test environment
docker-compose -f docker-compose.test.yml up

# Run tests in isolation
docker-compose -f docker-compose.test.yml run test-runner

# Clean up
docker-compose -f docker-compose.test.yml down
```

### Manual Testing

```bash
# 1. Generate test data
python fixtures.py

# 2. Start dashboard (in separate terminal)
cd ..
streamlit run app.py

# 3. Run tests
python -m pytest test_streamlit_components.py -v  # Unit tests
python -m pytest test_selenium_e2e.py -v          # E2E tests
python ai_visual_analyzer.py                      # Visual analysis
```

## Test Data

### Default Test Users
- **admin/admin123** - Default administrator
- **testuser/testpass123** - Regular user
- **viewer/viewonly456** - View-only user
- **analyst/analyst789** - Admin analyst

### Test Database
The test database includes:
- 8 different model evaluations
- 30 days of historical data
- 21 different test suites
- Performance metrics and rankings

## Visual Testing

### Capturing Baselines
When running visual tests for the first time, baseline images are automatically captured:

```python
visual_tester = VisualRegressionTest()
screenshot = visual_tester.capture_screenshot(driver, "dashboard_initial")
result = visual_tester.compare_visual(screenshot, "dashboard_initial")
```

### AI Agent Analysis
Screenshots can be analyzed by AI agents for:
- Layout issues
- Color contrast problems
- Missing components
- Accessibility concerns
- Responsive design issues

```python
analyzer = AIVisualAnalyzer()
result = analyzer.analyze_with_claude(screenshot_path, context="Login page")
```

## CI/CD Integration

### GitHub Actions Workflow
The dashboard tests run automatically on:
- Push to main or sleeper-refine branches
- Pull requests affecting dashboard code
- Manual workflow dispatch

### Test Jobs
1. **unit-tests** - Runs component unit tests with coverage
2. **e2e-tests** - Runs Selenium E2E tests in containers
3. **visual-regression** - Analyzes screenshots with AI
4. **dashboard-integration** - Tests Docker container health
5. **test-summary** - Aggregates results

### Artifacts
Test runs generate artifacts including:
- Coverage reports
- Screenshots
- Test reports (HTML)
- Container logs
- AI analysis results

## Troubleshooting

### Common Issues

#### Dashboard Not Accessible
```bash
# Check if dashboard is running
curl http://localhost:8501/_stcore/health

# Check Docker logs
docker-compose logs dashboard
```

#### Selenium Connection Failed
```bash
# Ensure Chrome driver is installed
pip install webdriver-manager

# Or use Docker Selenium
docker run -d -p 4444:4444 selenium/standalone-chrome
```

#### Visual Test Failures
```bash
# Update baselines if UI changed intentionally
rm -rf baselines/*.png
./run_tests.sh visual  # Will create new baselines
```

#### Permission Issues
```bash
# Fix directory permissions
chmod -R 755 screenshots/ baselines/ ai_feedback/
```

## Best Practices

### Writing New Tests

1. **Unit Tests**: Focus on component logic, use mocks for external dependencies
2. **E2E Tests**: Test complete user workflows, capture meaningful screenshots
3. **Visual Tests**: Maintain updated baselines, document intentional UI changes
4. **Performance**: Set reasonable timeouts, use explicit waits over sleep

### Test Data Management

1. Use fixtures for consistent test data
2. Clean up test artifacts after runs
3. Don't commit large screenshot files
4. Use separate test databases

### AI Integration

1. Provide clear context for AI analysis
2. Review AI feedback for false positives
3. Use multiple AI agents for comparison
4. Save analysis results for tracking

## Configuration

### Environment Variables

```bash
# Dashboard URL for testing
export DASHBOARD_URL=http://localhost:8501

# Selenium configuration
export SELENIUM_URL=http://localhost:4444

# Enable headless mode
export HEADLESS=true

# Database paths
export DATABASE_PATH=/path/to/test.db
export AUTH_DB_PATH=/path/to/test_users.db
```

### Test Settings

Edit `pytest.ini` for pytest configuration:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --strict-markers
```

## Extending Tests

### Adding New Test Cases

1. Create test method in appropriate test file
2. Use descriptive names following convention
3. Add docstrings explaining test purpose
4. Capture screenshots for visual tests
5. Update fixtures if new data needed

### Custom Assertions

```python
def assert_dashboard_loaded(driver):
    """Custom assertion for dashboard state."""
    assert "Sleeper Detection Dashboard" in driver.title
    assert driver.find_element(By.TAG_NAME, "h1")
```

### Integration with New AI Agents

```python
def analyze_with_custom_agent(screenshot_path, prompt):
    """Add support for new AI agent."""
    # Implement agent-specific API call
    pass
```

## Metrics and Reporting

### Coverage Goals
- Unit tests: >80% coverage
- E2E tests: All critical user paths
- Visual tests: All major UI states

### Performance Targets
- Page load: <3 seconds
- Chart render: <2 seconds
- Navigation: <1 second

### Quality Gates
- All tests must pass for PR merge
- Visual regression threshold: <5% difference
- No critical accessibility issues

## Support

For issues or questions about testing:
1. Check this documentation
2. Review test output logs
3. Examine CI/CD artifacts
4. Consult AI agent analysis results
