# CGT Validator Makefile
# Simplifies common development tasks

.PHONY: help build test lint format clean docker-build docker-up docker-down install dev-install

# Default target
help:
	@echo "CGT Validator Development Commands"
	@echo "================================="
	@echo "make install       - Install production dependencies"
	@echo "make dev-install   - Install development dependencies"
	@echo "make test          - Run all tests"
	@echo "make test-fast     - Run tests without coverage"
	@echo "make lint          - Run linting checks"
	@echo "make format        - Auto-format code"
	@echo "make clean         - Remove build artifacts"
	@echo "make pre-commit    - Run pre-commit hooks"
	@echo ""
	@echo "Docker Commands:"
	@echo "make docker-build  - Build Docker images"
	@echo "make docker-up     - Start all services"
	@echo "make docker-down   - Stop all services"
	@echo "make docker-test   - Run tests in Docker"
	@echo "make docker-shell  - Open shell in dev container"
	@echo ""
	@echo "Validation Commands:"
	@echo "make validate-oregon - Run Oregon validation demo"
	@echo "make validate FILE=path/to/file.xlsx STATE=oregon - Validate custom file"

# Installation
install:
	pip install -r requirements-cgt.txt
	pip install -e .

dev-install: install
	pip install black flake8 pylint mypy pytest pytest-cov pytest-benchmark pre-commit
	pre-commit install

# Testing
test:
	PYTHONPATH=src pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing

test-fast:
	PYTHONPATH=src pytest tests/ -v

test-integration:
	PYTHONPATH=src python test_oregon.py
	PYTHONPATH=src python test_validation_demo.py

# Code quality
lint:
	black --check src tests
	flake8 src tests --max-line-length=120 --extend-ignore=E203,W503
	pylint src --disable=R,C --max-line-length=120
	mypy src --ignore-missing-imports

format:
	black src tests
	isort src tests

# Pre-commit hooks
pre-commit:
	pre-commit run --all-files

pre-commit-update:
	pre-commit autoupdate

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

# Docker commands
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

docker-shell:
	docker-compose run --rm cgt-dev /bin/bash

docker-logs:
	docker-compose logs -f

# Validation shortcuts
validate-oregon:
	PYTHONPATH=src cgt-validate validate oregon --file mock_data/oregon/test_submission.xlsx --output oregon_report.html

validate:
ifndef FILE
	$(error FILE is not set. Usage: make validate FILE=path/to/file.xlsx STATE=oregon)
endif
ifndef STATE
	$(error STATE is not set. Usage: make validate FILE=path/to/file.xlsx STATE=oregon)
endif
	PYTHONPATH=src cgt-validate validate $(STATE) --file $(FILE) --output validation_report.html

# Development shortcuts
run-scraper:
	PYTHONPATH=src python -m scrapers.scheduler run --all-states

generate-mock-data:
	PYTHONPATH=src python -m mock_data.oregon_generator

# Release management
version:
	@python setup.py --version

changelog:
	@echo "Recent changes:"
	@git log --oneline -10

# CI simulation
ci-local:
	@echo "Running CI pipeline locally..."
	make lint
	make test
	make docker-build
	@echo "CI pipeline complete!"
