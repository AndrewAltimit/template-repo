# GitHub AI Agents Test Suite

## Structure

The test suite is organized into four categories:

### Unit Tests (`unit/`)
Fast, isolated tests for individual components. No external dependencies.
- `test_agents.py` - Agent interface and availability tests
- `test_security.py` - Security manager and authorization tests

**Run with:**
```bash
pytest tests/unit -v
```

**Coverage target:** >90%

### Integration Tests (`integration/`)
Tests for component interactions. May use mocked GitHub API.
- `test_issue_monitor.py` - Issue monitoring workflow tests
- `test_pr_monitor.py` - PR monitoring workflow tests
- `test_monitors.py` - Monitor integration tests
- `test_subagents.py` - Subagent system tests

**Run with:**
```bash
pytest tests/integration -v
```

**Coverage target:** >80%

### End-to-End Tests (`e2e/`)
Full workflow tests. May require GitHub credentials.

**Run with:**
```bash
pytest tests/e2e -v
```

**Requires:** `GITHUB_TOKEN` environment variable

### TTS Tests (`tts/`)
Text-to-speech integration tests.
- `test_tts_integration.py` - TTS integration tests
- `test_tts_unit.py` - TTS unit tests
- `test_voice_profiles.py` - Voice profile tests

**Run with:**
```bash
pytest tests/tts -v
```

## Running Tests

### All Tests
```bash
pytest tests/ -v --cov=github_ai_agents
```

### Specific Categories
```bash
pytest tests/unit -v          # Unit tests only
pytest tests/integration -v   # Integration tests only
pytest tests/e2e -v           # E2E tests only
pytest tests/tts -v           # TTS tests only
```

### With Coverage
```bash
pytest tests/ --cov=github_ai_agents --cov-report=html
```

### Quick Test (Unit + Integration, No TTS)
```bash
pytest tests/unit tests/integration -v
```

### Using Docker (Recommended)
```bash
docker-compose run --rm python-ci pytest tests/ -v --cov=.
```

## Fixtures

See `conftest.py` for available fixtures:

### Agent Fixtures
- `mock_claude_agent` - Mock Claude agent
- `mock_opencode_agent` - Mock OpenCode agent
- `mock_gemini_agent` - Mock Gemini agent
- `mock_crush_agent` - Mock Crush agent

### Subagent Fixtures
- `mock_tech_lead_agent` - Mock tech lead subagent
- `mock_security_auditor_agent` - Mock security auditor subagent
- `mock_qa_reviewer_agent` - Mock QA reviewer subagent

### Security Fixtures
- `mock_security_manager` - Mock security manager

### GitHub API Fixtures
- `mock_github_issue` - Sample GitHub issue data
- `mock_github_pr` - Sample GitHub PR data
- `mock_github_comment` - Sample GitHub comment data
- `mock_github_api` - Mock GitHub API client

### Environment Fixtures
- `mock_env_vars` - Mock environment variables
- `test_repo_name` - Test repository name
- `test_repo_owner` - Test repository owner

### Test Data Fixtures
- `sample_code` - Sample Python code
- `sample_issue_body_approved` - Sample approved issue body
- `sample_pr_review_comment` - Sample PR review comment

## Writing Tests

Follow these patterns:

### Unit Test Pattern
```python
def test_agent_availability(mock_claude_agent):
    """Test agent availability check."""
    assert mock_claude_agent.is_available() is True
    assert mock_claude_agent.get_trigger_keyword() == "Claude"
```

### Integration Test Pattern
```python
async def test_issue_processing(mock_github_issue, mock_claude_agent):
    """Test full issue processing workflow."""
    # Setup
    issue = mock_github_issue
    agent = mock_claude_agent

    # Execute
    result = await process_issue(issue, agent)

    # Verify
    assert result.success is True
    agent.generate_code.assert_called_once()
```

### E2E Test Pattern
```python
@pytest.mark.e2e
async def test_full_workflow(mock_env_vars):
    """Test complete issue-to-PR workflow."""
    # Requires actual GitHub credentials
    # Tests full workflow from issue detection to PR creation
    pass
```

### Using Multiple Fixtures
```python
async def test_multi_agent_workflow(
    mock_claude_agent,
    mock_opencode_agent,
    mock_security_manager,
    mock_github_issue
):
    """Test workflow with multiple agents and security."""
    # Test implementation
    pass
```

## Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.unit
def test_something():
    """Unit test."""
    pass

@pytest.mark.integration
async def test_integration():
    """Integration test."""
    pass

@pytest.mark.e2e
async def test_end_to_end():
    """E2E test."""
    pass

@pytest.mark.slow
def test_slow_operation():
    """Test that takes a long time."""
    pass
```

**Run specific markers:**
```bash
pytest -v -m unit          # Run only unit tests
pytest -v -m "not slow"    # Skip slow tests
pytest -v -m "unit or integration"  # Run unit and integration
```

## Coverage Requirements

- **Overall Package:** >80%
- **Unit Tests:** >90% coverage of tested modules
- **Integration Tests:** >80% coverage of tested workflows
- **Critical Paths:** 100% coverage (security, authorization)

**Generate HTML coverage report:**
```bash
pytest tests/ --cov=github_ai_agents --cov-report=html
open htmlcov/index.html
```

## Continuous Integration

Tests run automatically in GitHub Actions:
- On every push to PR branches
- On every PR to main branch
- Scheduled daily runs on main branch

**CI Commands:**
```bash
# Format check
./automation/ci-cd/run-ci.sh format

# Linting
./automation/ci-cd/run-ci.sh lint-basic

# Full test suite with coverage
./automation/ci-cd/run-ci.sh test
```

## Troubleshooting

### Import Errors
If you encounter import errors, ensure the package is installed:
```bash
pip install -e packages/github_ai_agents
```

### Environment Variables
Many tests require environment variables. Use `mock_env_vars` fixture or set manually:
```bash
export GITHUB_TOKEN=your_token_here
export GITHUB_REPOSITORY=owner/repo
```

### Async Test Issues
Ensure you're using `pytest-asyncio`:
```bash
pip install pytest-asyncio
```

Mark async tests with:
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

### Fixture Not Found
If a fixture is not found, check:
1. Fixture is defined in `conftest.py`
2. Fixture name is spelled correctly
3. `conftest.py` is in the tests root directory

## Best Practices

1. **Isolate Tests:** Each test should be independent
2. **Use Fixtures:** Reuse fixtures instead of duplicating setup code
3. **Mock External Calls:** Always mock GitHub API and external services
4. **Clear Test Names:** Use descriptive test function names
5. **Test Edge Cases:** Don't just test the happy path
6. **Keep Tests Fast:** Unit tests should run in milliseconds
7. **Document Complex Tests:** Add docstrings explaining what's being tested
8. **Clean Up:** Use fixtures for teardown when needed

## Adding New Tests

When adding new tests:

1. Choose the correct directory (unit/integration/e2e/tts)
2. Follow the naming convention: `test_<feature>.py`
3. Use existing fixtures from `conftest.py` when possible
4. Add new fixtures to `conftest.py` if needed
5. Update this README if adding a new test category
6. Ensure tests pass locally before committing:
   ```bash
   pytest tests/ -v
   ```

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [Package Documentation](../docs/INDEX.md)
