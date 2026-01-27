#!/bin/bash
# Script to properly run Docker tests for the dashboard
# This ensures the correct build context for both images

set -e

echo "Building and running dashboard tests with Docker..."

# Change to tests directory for proper context
cd tests

# Build and run with docker-compose
docker compose -f docker-compose.test.yml build
docker compose -f docker-compose.test.yml up --abort-on-container-exit

# Clean up
docker compose -f docker-compose.test.yml down

echo "Tests completed!"
