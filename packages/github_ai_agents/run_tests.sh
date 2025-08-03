#!/bin/bash
# Run tests for the github_ai_agents package

set -e

echo "Running tests for github_ai_agents package..."

# Ensure we're in the package directory
cd "$(dirname "$0")"

# Install the package in development mode if not already installed
echo "Installing package in development mode..."
pip install -e ".[dev]"

# Run tests with coverage
echo "Running tests with coverage..."
python -m pytest tests/ -v --cov=github_ai_agents --cov-report=term-missing --cov-report=html

echo "Tests completed! Coverage report available in htmlcov/index.html"
