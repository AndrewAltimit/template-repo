#!/bin/bash
# Export versions from versions.json as environment variables for Docker builds
#
# This script reads versions from config/versions.json and exports them as
# environment variables that can be used by docker-compose build commands.
# This ensures Docker images always use the centralized version configuration.

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Path to versions.json
VERSIONS_FILE="$PROJECT_ROOT/config/versions.json"

# Check if versions.json exists
if [ ! -f "$VERSIONS_FILE" ]; then
    echo "Error: versions.json not found at $VERSIONS_FILE" >&2
    exit 1
fi

# Function to extract version for a given DBR version and tool
get_version() {
    local dbr_version=$1
    local tool=$2
    jq -r ".${dbr_version}.\"${tool}\" // empty" "$VERSIONS_FILE"
}

# Export DBR15 versions
DBX_CLI_VERSION_DBR15=$(get_version "dbr15" "databricks-cli")
TERRAFORM_VERSION_DBR15=$(get_version "dbr15" "terraform")
TERRAGRUNT_VERSION_DBR15=$(get_version "dbr15" "terragrunt")
AWS_CLI_VERSION_DBR15=$(get_version "dbr15" "aws-cli")
export DBX_CLI_VERSION_DBR15
export TERRAFORM_VERSION_DBR15
export TERRAGRUNT_VERSION_DBR15
export AWS_CLI_VERSION_DBR15
# Note: UV version is hardcoded in Dockerfile due to Docker limitation with COPY --from

# Export DBR16 versions
DBX_CLI_VERSION_DBR16=$(get_version "dbr16" "databricks-cli")
TERRAFORM_VERSION_DBR16=$(get_version "dbr16" "terraform")
TERRAGRUNT_VERSION_DBR16=$(get_version "dbr16" "terragrunt")
AWS_CLI_VERSION_DBR16=$(get_version "dbr16" "aws-cli")
export DBX_CLI_VERSION_DBR16
export TERRAFORM_VERSION_DBR16
export TERRAGRUNT_VERSION_DBR16
export AWS_CLI_VERSION_DBR16
# Note: UV version is hardcoded in Dockerfile due to Docker limitation with COPY --from

# Print exported variables (useful for debugging)
if [ "${DEBUG:-0}" = "1" ]; then
    echo "Exported versions from $VERSIONS_FILE:"
    echo "DBR15:"
    echo "  DBX_CLI_VERSION_DBR15=$DBX_CLI_VERSION_DBR15"
    echo "  TERRAFORM_VERSION_DBR15=$TERRAFORM_VERSION_DBR15"
    echo "  TERRAGRUNT_VERSION_DBR15=$TERRAGRUNT_VERSION_DBR15"
    echo "  AWS_CLI_VERSION_DBR15=$AWS_CLI_VERSION_DBR15"
    echo "DBR16:"
    echo "  DBX_CLI_VERSION_DBR16=$DBX_CLI_VERSION_DBR16"
    echo "  TERRAFORM_VERSION_DBR16=$TERRAFORM_VERSION_DBR16"
    echo "  TERRAGRUNT_VERSION_DBR16=$TERRAGRUNT_VERSION_DBR16"
    echo "  AWS_CLI_VERSION_DBR16=$AWS_CLI_VERSION_DBR16"
fi
