#!/bin/bash
# Script to validate that Python cache prevention measures are properly configured

set -e

echo "🔍 Validating Python Cache Prevention Configuration"
echo "=================================================="

ERRORS=0
WARNINGS=0

# Function to check file for required environment variables
check_dockerfile() {
    local file="$1"
    local required_vars=("PYTHONDONTWRITEBYTECODE" "PYTHONPYCACHEPREFIX")
    
    echo "Checking Dockerfile: $file"
    for var in "${required_vars[@]}"; do
        if grep -q "ENV $var" "$file"; then
            echo "  ✅ $var is set"
        else
            echo "  ❌ Missing: ENV $var"
            ((ERRORS++))
        fi
    done
}

# Function to check docker-compose services
check_docker_compose() {
    local file="$1"
    echo "Checking docker-compose.yml for Python services..."
    
    # Check python-ci service
    if grep -A10 "python-ci:" "$file" | grep -q "PYTHONDONTWRITEBYTECODE"; then
        echo "  ✅ python-ci has PYTHONDONTWRITEBYTECODE"
    else
        echo "  ⚠️  python-ci missing PYTHONDONTWRITEBYTECODE"
        ((WARNINGS++))
    fi
    
    # Check mcp-server service
    if grep -A10 "mcp-server:" "$file" | grep -q "PYTHONDONTWRITEBYTECODE"; then
        echo "  ✅ mcp-server has PYTHONDONTWRITEBYTECODE"
    else
        echo "  ⚠️  mcp-server missing PYTHONDONTWRITEBYTECODE"
        ((WARNINGS++))
    fi
}

# Check all Dockerfiles
echo ""
echo "1. Checking Dockerfiles..."
echo "--------------------------"
for dockerfile in docker/*.Dockerfile; do
    if [[ -f "$dockerfile" ]] && grep -q "python" "$dockerfile"; then
        check_dockerfile "$dockerfile"
    fi
done

# Check docker-compose.yml
echo ""
echo "2. Checking docker-compose.yml..."
echo "---------------------------------"
if [[ -f "docker-compose.yml" ]]; then
    check_docker_compose "docker-compose.yml"
else
    echo "  ❌ docker-compose.yml not found"
    ((ERRORS++))
fi

# Check pytest.ini
echo ""
echo "3. Checking pytest configuration..."
echo "-----------------------------------"
if [[ -f "pytest.ini" ]]; then
    if grep -q "no:cacheprovider" "pytest.ini"; then
        echo "  ✅ pytest cache provider disabled"
    else
        echo "  ❌ pytest cache provider not disabled"
        ((ERRORS++))
    fi
else
    echo "  ⚠️  pytest.ini not found"
    ((WARNINGS++))
fi

# Check .dockerignore
echo ""
echo "4. Checking .dockerignore..."
echo "----------------------------"
if [[ -f ".dockerignore" ]]; then
    if grep -q "__pycache__" ".dockerignore"; then
        echo "  ✅ __pycache__ in .dockerignore"
    else
        echo "  ⚠️  __pycache__ not in .dockerignore"
        ((WARNINGS++))
    fi
else
    echo "  ⚠️  .dockerignore not found"
    ((WARNINGS++))
fi

# Check CI scripts
echo ""
echo "5. Checking CI scripts..."
echo "-------------------------"
if [[ -f "scripts/run-ci.sh" ]]; then
    if grep -q "PYTHONDONTWRITEBYTECODE" "scripts/run-ci.sh"; then
        echo "  ✅ run-ci.sh exports PYTHONDONTWRITEBYTECODE"
    else
        echo "  ⚠️  run-ci.sh doesn't export PYTHONDONTWRITEBYTECODE"
        ((WARNINGS++))
    fi
fi

# Summary
echo ""
echo "=================================================="
echo "Validation Summary:"
echo "  Errors: $ERRORS"
echo "  Warnings: $WARNINGS"

if [[ $ERRORS -eq 0 ]]; then
    if [[ $WARNINGS -eq 0 ]]; then
        echo "  ✅ All checks passed! Python cache prevention is properly configured."
    else
        echo "  ⚠️  Configuration is functional but could be improved."
    fi
    exit 0
else
    echo "  ❌ Critical issues found. Please fix the errors above."
    exit 1
fi