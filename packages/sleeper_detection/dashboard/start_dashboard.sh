#!/bin/bash
# Alternative method using the test docker-compose

PASSWORD="${1:-kbvuej4326hgUO8f}"

# Clean up any existing database
rm -f tests/test_evaluation_results.db 2>/dev/null

# Start using test docker-compose
cd tests
export DASHBOARD_ADMIN_PASSWORD="$PASSWORD"
docker-compose -f docker-compose.test.yml up dashboard

# The dashboard will be available at http://localhost:8501
# Username: admin
# Password: $PASSWORD
