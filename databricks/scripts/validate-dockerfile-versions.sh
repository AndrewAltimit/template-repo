#!/bin/bash
# Validate that UV versions in Dockerfiles match versions.json
# This prevents version drift since Docker doesn't support ARG in COPY --from

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Find the databricks directory
if [ -d "databricks" ]; then
    DATABRICKS_DIR="databricks"
elif [ -d "../databricks" ]; then
    DATABRICKS_DIR="../databricks"
else
    echo -e "${RED}Error: Cannot find databricks directory${NC}"
    exit 1
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is required to parse versions.json${NC}"
    exit 1
fi

# Check if versions.json exists
VERSIONS_FILE="${DATABRICKS_DIR}/config/versions.json"
if [ ! -f "$VERSIONS_FILE" ]; then
    echo -e "${RED}Error: versions.json not found at $VERSIONS_FILE${NC}"
    exit 1
fi

# Function to validate UV version for a specific DBR version
validate_uv_version() {
    local dbr_version=$1
    local dockerfile="${DATABRICKS_DIR}/docker/dockerfiles/${dbr_version}.Dockerfile"

    if [ ! -f "$dockerfile" ]; then
        echo -e "${YELLOW}Warning: Dockerfile not found at $dockerfile${NC}"
        return 0
    fi

    # Extract UV version from Dockerfile
    local uv_version_df
    uv_version_df=$(grep "ghcr.io/astral-sh/uv:" "$dockerfile" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)

    if [ -z "$uv_version_df" ]; then
        echo -e "${RED}Error: Could not extract UV version from $dockerfile${NC}"
        return 1
    fi

    # Extract UV version from versions.json
    local uv_version_json
    uv_version_json=$(jq -r ".${dbr_version}.uv" "$VERSIONS_FILE")

    if [ "$uv_version_json" = "null" ] || [ -z "$uv_version_json" ]; then
        echo -e "${YELLOW}Warning: UV version not found in versions.json for ${dbr_version}${NC}"
        return 0
    fi

    # Compare versions
    if [ "$uv_version_df" != "$uv_version_json" ]; then
        echo -e "${RED}Error: UV version mismatch for ${dbr_version}${NC}"
        echo -e "  Dockerfile: ${uv_version_df}"
        echo -e "  versions.json: ${uv_version_json}"
        return 1
    else
        echo -e "${GREEN}✓ UV versions match for ${dbr_version}: ${uv_version_df}${NC}"
        return 0
    fi
}

# Function to validate other tool versions in Dockerfiles
validate_tool_versions() {
    local dbr_version=$1
    local dockerfile="${DATABRICKS_DIR}/docker/dockerfiles/${dbr_version}.Dockerfile"

    if [ ! -f "$dockerfile" ]; then
        return 0
    fi

    # Tools to check
    local tools=("databricks-cli" "terraform" "terragrunt" "aws-cli")
    local arg_names=("DBX_CLI_VERSION" "TERRAFORM_VERSION" "TERRAGRUNT_VERSION" "AWS_CLI_VERSION")

    local has_error=false

    for i in "${!tools[@]}"; do
        local tool="${tools[$i]}"
        local arg_name="${arg_names[$i]}"

        # Extract version from Dockerfile ARG
        local version_df
        version_df=$(grep "^ARG ${arg_name}=" "$dockerfile" | cut -d'=' -f2)

        if [ -z "$version_df" ]; then
            echo -e "${YELLOW}Warning: ${arg_name} not found in ${dbr_version} Dockerfile${NC}"
            continue
        fi

        # Extract version from versions.json
        local version_json
        version_json=$(jq -r ".${dbr_version}.\"${tool}\"" "$VERSIONS_FILE")

        if [ "$version_json" = "null" ] || [ -z "$version_json" ]; then
            echo -e "${YELLOW}Warning: ${tool} version not found in versions.json for ${dbr_version}${NC}"
            continue
        fi

        # Compare versions
        if [ "$version_df" != "$version_json" ]; then
            echo -e "${RED}Error: ${tool} version mismatch for ${dbr_version}${NC}"
            echo -e "  Dockerfile ARG: ${version_df}"
            echo -e "  versions.json: ${version_json}"
            has_error=true
        else
            echo -e "${GREEN}✓ ${tool} versions match for ${dbr_version}: ${version_df}${NC}"
        fi
    done

    if [ "$has_error" = true ]; then
        return 1
    fi
    return 0
}

# Main validation
echo "Validating Dockerfile versions against versions.json..."
echo ""

EXIT_CODE=0

# Validate DBR15
echo "Checking DBR15..."
if ! validate_uv_version "dbr15"; then
    EXIT_CODE=1
fi
if ! validate_tool_versions "dbr15"; then
    EXIT_CODE=1
fi
echo ""

# Validate DBR16
echo "Checking DBR16..."
if ! validate_uv_version "dbr16"; then
    EXIT_CODE=1
fi
if ! validate_tool_versions "dbr16"; then
    EXIT_CODE=1
fi

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ All version checks passed!${NC}"
else
    echo ""
    echo -e "${RED}✗ Version validation failed!${NC}"
    echo -e "${YELLOW}Please update the Dockerfiles to match versions.json${NC}"
fi

exit $EXIT_CODE
