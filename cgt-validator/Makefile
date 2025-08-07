# CGT Validator Makefile
# Container-First Development Approach
# All primary targets use Docker by default

.PHONY: help build test lint format clean docker-build docker-up docker-down install dev-install

# Default target
help:
	@echo "CGT Validator Development Commands (Container-First)"
	@echo "===================================================="
	@echo ""
	@echo "Primary Commands (use Docker):"
	@echo "  make test          - Run all tests in Docker"
	@echo "  make test-fast     - Run tests without coverage in Docker"
	@echo "  make lint          - Run linting checks in Docker"
	@echo "  make format        - Auto-format code in Docker"
	@echo "  make clean         - Remove build artifacts"
	@echo "  make validate      - Run validation with Docker"
	@echo ""
	@echo "Docker Management:"
	@echo "  make build         - Build Docker images"
	@echo "  make up            - Start all services"
	@echo "  make down          - Stop all services"
	@echo "  make shell         - Open shell in dev container"
	@echo "  make logs          - View service logs"
	@echo ""
	@echo "Local Development (discouraged - use containers):"
	@echo "  make local-install - Install locally (not recommended)"
	@echo "  make local-test    - Run tests locally (not recommended)"
	@echo "  make local-lint    - Run linting locally (not recommended)"
	@echo ""
	@echo "Validation Commands:"
	@echo "  make validate-oregon - Run Oregon validation demo"
	@echo "  make validate FILE=path/to/file.xlsx STATE=oregon"

# Container-first commands (default)
test: docker-test

test-fast:
	docker-compose run --rm cgt-test pytest tests/ -v

lint: docker-lint

format: docker-format

# Docker commands
build: docker-build

up: docker-up

down: docker-down

shell: docker-shell

logs: docker-logs

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-test:
	docker-compose run --rm cgt-test

docker-lint:
	docker-compose run --rm cgt-lint

docker-format:
	docker-compose run --rm cgt-dev black src tests
	docker-compose run --rm cgt-dev isort src tests

docker-shell:
	docker-compose run --rm cgt-dev /bin/bash

docker-logs:
	docker-compose logs -f

# Validation shortcuts (using containers)
validate-oregon:
	docker-compose run --rm cgt-dev cgt-validate validate oregon --file mock_data/oregon/test_submission.xlsx --output oregon_report.html

validate:
ifndef FILE
	$(error FILE is not set. Usage: make validate FILE=path/to/file.xlsx STATE=oregon)
endif
ifndef STATE
	$(error STATE is not set. Usage: make validate FILE=path/to/file.xlsx STATE=oregon)
endif
	docker-compose run --rm cgt-dev cgt-validate validate $(STATE) --file $(FILE) --output validation_report.html

# Development shortcuts (using containers)
run-scraper:
	docker-compose run --rm cgt-dev python -m scrapers.scheduler run --all-states

generate-mock-data:
	docker-compose run --rm cgt-dev python -m mock_data.oregon_generator

monitor-templates:
	docker-compose run --rm cgt-dev cgt-monitor monitor-all

check-critical:
	docker-compose run --rm cgt-dev cgt-check-critical

# Local commands (discouraged - prefer container commands above)
local-install:
	@echo "⚠️  WARNING: Local installation is discouraged. Use Docker instead."
	@echo "To proceed anyway, run: pip install -r requirements-cgt.txt && pip install -e ."

local-dev-install: local-install
	@echo "⚠️  WARNING: Local installation is discouraged. Use Docker instead."
	pip install black flake8 pylint mypy pytest pytest-cov pytest-benchmark pre-commit
	pre-commit install

local-test:
	@echo "⚠️  WARNING: Running tests locally is discouraged. Use 'make test' instead."
	PYTHONPATH=src pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing

local-lint:
	@echo "⚠️  WARNING: Running lint locally is discouraged. Use 'make lint' instead."
	black --check src tests
	flake8 src tests
	pylint src --disable=R,C --max-line-length=120
	mypy src --ignore-missing-imports

# Pre-commit hooks
pre-commit:
	docker-compose run --rm cgt-dev pre-commit run --all-files

pre-commit-update:
	docker-compose run --rm cgt-dev pre-commit autoupdate

# Cleaning
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	rm -f test_report*.html
	rm -f validation_demo_report.html
	rm -f critical_changes.json

# Release management
version:
	@docker-compose run --rm cgt-dev python setup.py --version

changelog:
	@echo "Recent changes:"
	@git log --oneline -10

# CI simulation (uses containers)
ci-local:
	@echo "Running CI pipeline locally (container-based)..."
	make lint
	make test
	make build
	@echo "CI pipeline complete!"
