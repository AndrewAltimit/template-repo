# Pre-commit Hooks Added to CGT Validator

## What Was Added

### 1. Pre-commit Configuration (`.pre-commit-config.yaml`)

Comprehensive hooks for code quality:

#### Python Code Quality
- **Black** - Automatic code formatting (120 char lines)
- **isort** - Import sorting with Black-compatible profile
- **Flake8** - Style guide enforcement
- **MyPy** - Static type checking with type stubs
- **Bandit** - Security vulnerability scanning
- **reorder-python-imports** - Additional import cleanup

#### General File Quality
- Trailing whitespace removal
- End-of-file fixing
- Large file detection (5MB limit for Excel files)
- Merge conflict detection
- Case conflict detection
- Mixed line ending fixes (LF)
- JSON formatting
- Private key detection

#### Language-Specific
- **YAML** - yamllint with custom rules
- **Shell** - ShellCheck for bash scripts
- **Markdown** - markdownlint with relaxed rules
- **Docker** - Hadolint for best practices
- **GitHub Actions** - actionlint for workflow validation

#### Project-Specific Hooks
- **Check hardcoded states** - Ensures state names use config
- **Validator test check** - Each validator must have tests
- **Mock data validation** - Validates Excel file structure

### 2. Configuration Files

#### `.yamllint.yml`
- 150 char line limit for GitHub Actions
- 2-space indentation
- Flexible string quoting
- Ignores common build directories

#### `.flake8`
- 120 char line limit
- Black-compatible ignores (E203, W503)
- Per-file ignores for `__init__.py` and tests

### 3. Helper Scripts

#### `scripts/install-pre-commit.sh`
```bash
# One-command setup
./scripts/install-pre-commit.sh
```

#### `scripts/check-validator-tests.sh`
- Ensures each validator has corresponding test file
- Called automatically by pre-commit

#### `scripts/validate-mock-data.py`
- Validates Excel files have required sheets
- Checks basic structure integrity

### 4. Updated Files

#### `Makefile`
```bash
make pre-commit         # Run all hooks
make pre-commit-update  # Update hook versions
make dev-install        # Installs pre-commit automatically
```

#### `.gitignore`
- Added `.pre-commit-config.yaml.lock`
- Enhanced Python and project-specific ignores
- Better test output exclusions

#### GitHub Actions (`ci.yml`)
- Added dedicated `pre-commit` job
- Runs on all branches
- Shows diff on failures
- Cached for speed

## Usage

### First Time Setup
```bash
# Automatic with dev install
make dev-install

# Or manual
pip install pre-commit
pre-commit install
```

### Daily Usage
```bash
# Hooks run automatically on commit
git commit -m "feat: add new feature"

# Run manually on all files
make pre-commit

# Run on specific files
pre-commit run --files src/validators/*.py

# Skip hooks if needed
git commit --no-verify -m "WIP: emergency fix"
```

### Common Scenarios

#### Auto-formatting
```bash
# If Black or isort fails
make format
git add -u
git commit -m "style: format code"
```

#### Type Errors
```python
# Add type: ignore comment
result = complex_function()  # type: ignore

# Or add proper types
def process(data: pd.DataFrame) -> ValidationResults:
    ...
```

#### Large Files
```yaml
# In .pre-commit-config.yaml, adjust:
args: [--maxkb=10000]  # Allow 10MB files
```

## Benefits

1. **Consistent Code Style** - Black and isort ensure uniform formatting
2. **Early Bug Detection** - Type checking and linting catch issues
3. **Security** - Bandit and credential detection prevent leaks
4. **Clean History** - No more "fix formatting" commits
5. **CI Speed** - Issues caught locally, not in CI
6. **Team Alignment** - Everyone follows same standards

## Customization

### Skip Specific Hooks
```bash
# In commit
SKIP=mypy,bandit git commit -m "feat: quick prototype"

# In file
# pylint: disable=too-many-arguments
def complex_function(a, b, c, d, e, f):
    ...
```

### Project-Specific Rules
The configuration includes custom hooks for:
- Preventing hardcoded state names
- Ensuring test coverage
- Validating data file structure

These can be extended in `.pre-commit-config.yaml` under the `local` repo section.

## Integration with CI

The pre-commit checks now run in CI:
- Dedicated job in GitHub Actions
- Cached for performance
- Shows diffs for easy fixes
- Non-blocking (continue-on-error)

This ensures that even if developers skip hooks locally, CI will catch issues.

## Next Steps

1. Run `make dev-install` to set up hooks
2. Try `make pre-commit` to see current status
3. Fix any issues with `make format`
4. Commit with confidence!

The CGT Validator now has enterprise-grade code quality automation!
