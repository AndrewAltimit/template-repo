# CGT Validator Project Structure

## Overview

The CGT Validator is organized as a standalone Python package with comprehensive Docker support and CI/CD automation.

```
cgt-validator/
├── .github/                    # GitHub Actions workflows
│   └── workflows/
│       ├── ci.yml             # Comprehensive CI pipeline
│       ├── release.yml        # Release automation
│       ├── dependencies.yml   # Dependency updates
│       └── scheduled-scraping.yml  # Monthly scraping
├── docs/                      # User documentation
│   ├── installation.md
│   ├── user_guide.md
│   └── troubleshooting.md
├── src/                       # Source code
│   ├── __init__.py
│   ├── cli.py                # Command-line interface
│   ├── config/               # Configuration
│   │   ├── __init__.py
│   │   └── states_config.py  # State URLs and settings
│   ├── mock_data/            # Mock data generators
│   │   ├── __init__.py
│   │   └── oregon_generator.py
│   ├── parsers/              # Document parsers
│   │   ├── __init__.py
│   │   └── requirements_parser.py
│   ├── reporters/            # Report generators
│   │   ├── __init__.py
│   │   ├── excel_annotator.py
│   │   ├── html_reporter.py
│   │   ├── markdown_reporter.py
│   │   └── validation_results.py
│   ├── scrapers/             # Web scrapers
│   │   ├── __init__.py
│   │   ├── document_downloader.py
│   │   ├── scheduler.py
│   │   └── web_scraper.py
│   └── validators/           # State validators
│       ├── __init__.py
│       ├── base_validator.py
│       └── oregon.py
├── tests/                    # Test suite
│   ├── __init__.py
│   ├── conftest.py          # Pytest configuration
│   ├── test_cli.py
│   ├── fixtures/            # Test data
│   ├── parsers/
│   ├── reporters/
│   ├── scrapers/
│   └── validators/
├── mock_data/               # Generated mock data
│   └── oregon/
├── requirements/            # Downloaded requirements
│   └── oregon/
├── scripts/                 # Utility scripts
│   ├── setup_cron.sh
│   └── setup_windows_scheduler.ps1
├── .dockerignore           # Docker ignore patterns
├── .env.example            # Environment variables template
├── .gitignore             # Git ignore patterns
├── Dockerfile             # Multi-stage Docker image
├── Makefile               # Development shortcuts
├── README.md              # Project documentation
├── docker-compose.yml     # Service definitions
├── docker-compose.override.yml  # Development overrides
├── pytest.ini             # Pytest configuration
├── requirements-cgt.txt   # Python dependencies
├── requirements-core.txt  # Core dependencies only
├── setup.py              # Package installation
└── pyproject.toml        # Python project metadata
```

## Key Components

### 1. Validators (`src/validators/`)

Base validator provides common functionality:
- Sheet validation
- Column validation
- Data type checking
- Business rule validation

State-specific validators inherit from base and implement:
- Custom requirements loading
- State-specific business rules
- Cross-sheet validation

### 2. Scrapers (`src/scrapers/`)

Web scraping system:
- **WebScraper**: Finds documents on state websites
- **DocumentDownloader**: Downloads with version tracking
- **Scheduler**: Automates periodic scraping

### 3. Reporters (`src/reporters/`)

Multiple output formats:
- **HTMLReporter**: Interactive web reports
- **MarkdownReporter**: Documentation-friendly reports
- **ExcelAnnotator**: Highlights errors in source files
- **ValidationResults**: Common data structure

### 4. CLI (`src/cli.py`)

User interface providing:
- Single file validation
- Batch validation
- Multiple output formats
- Progress indicators

## Docker Architecture

### Production Image
- Multi-stage build for security and size
- Non-root user execution
- Health checks included
- All dependencies included

### Development Environment
- Hot reload support
- Jupyter notebook integration
- Testing in containers
- Linting and formatting

### Services
- `cgt-validator`: Main application
- `cgt-dev`: Development shell
- `cgt-test`: Test runner
- `cgt-lint`: Code quality
- `cgt-docs`: Documentation server
- `cgt-scraper`: Automated scraping
- `cgt-notebook`: Jupyter environment

## CI/CD Pipeline

### On Every Push
1. **Lint** - Code style and quality
2. **Test** - Multiple Python versions (3.8-3.12)
3. **Coverage** - Ensure >80% coverage
4. **Security** - Vulnerability scanning
5. **Docker** - Build and test images
6. **Benchmark** - Performance testing

### Scheduled
- **Weekly**: Dependency updates
- **Monthly**: Scrape state requirements
- **Daily**: Full CI validation

### Release Process
1. Tag with version (e.g., `v0.1.0`)
2. Build Python package
3. Build multi-arch Docker images
4. Create GitHub release
5. Publish to PyPI (if configured)
6. Push to Docker Hub (if configured)

## Development Workflow

### Quick Start
```bash
# Clone and setup
git clone <repo>
cd cgt-validator
make dev-install

# Run tests
make test

# Start Docker environment
make docker-up

# Open development shell
make docker-shell
```

### Adding a New State

1. Create validator in `src/validators/`
2. Add state config in `src/config/states_config.py`
3. Create tests in `tests/validators/`
4. Add mock data generator
5. Update documentation

### Testing Strategy

- **Unit Tests**: Individual components
- **Integration Tests**: Full validation flow
- **Performance Tests**: Large file handling
- **Docker Tests**: Container functionality

## Security Considerations

- Non-root Docker containers
- No hardcoded credentials
- Environment-based configuration
- Input validation on all user data
- Rate limiting for scrapers
- Security scanning in CI/CD

## Future Enhancements

- REST API for programmatic access
- Web UI for non-technical users
- Database for historical tracking
- Real-time validation feedback
- Automated state requirement updates
- Multi-tenant support
