#!/bin/bash
# Common functions for corporate proxy scripts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo "========================================"
    echo "$1"
    echo "========================================"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Check if Docker is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        exit 1
    fi
}

# Check if required environment variables are set
check_env_vars() {
    local required_vars=("$@")
    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        print_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        return 1
    fi
    return 0
}

# Wait for service to be healthy
wait_for_service() {
    local url=$1
    local max_attempts=${2:-30}
    local service_name=${3:-"service"}

    print_info "Waiting for $service_name to be ready..."

    for i in $(seq 1 $max_attempts); do
        if curl -s "$url" > /dev/null 2>&1; then
            print_info "✓ $service_name is ready"
            return 0
        fi
        sleep 1
    done

    print_error "$service_name failed to start after $max_attempts seconds"
    return 1
}

# Build Docker image if not exists
build_if_needed() {
    local image_name=$1
    local dockerfile=$2
    local build_context=${3:-.}

    if ! docker image inspect "$image_name" >/dev/null 2>&1; then
        print_info "Image $image_name not found. Building..."
        docker build -f "$dockerfile" -t "$image_name" "$build_context"
        if [ $? -ne 0 ]; then
            print_error "Failed to build $image_name"
            exit 1
        fi
        print_info "Successfully built $image_name"
    else
        print_info "Using existing image $image_name"
    fi
}

# Stop and remove container if exists
cleanup_container() {
    local container_name=$1

    if docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        print_info "Stopping existing container $container_name..."
        docker stop "$container_name" >/dev/null 2>&1
        docker rm "$container_name" >/dev/null 2>&1
    fi
}

# Get the script's directory (works with symlinks)
get_script_dir() {
    local source="${BASH_SOURCE[0]}"
    while [ -h "$source" ]; do
        local dir="$( cd -P "$( dirname "$source" )" && pwd )"
        source="$(readlink "$source")"
        [[ $source != /* ]] && source="$dir/$source"
    done
    echo "$( cd -P "$( dirname "$source" )" && pwd )"
}

# Load configuration from JSON file
load_json_config() {
    local config_file=$1
    local query=$2

    if [ ! -f "$config_file" ]; then
        print_error "Configuration file not found: $config_file"
        return 1
    fi

    jq -r "$query" "$config_file" 2>/dev/null
}

# Export common paths
export CORPORATE_PROXY_ROOT="$(cd "$(get_script_dir)/../.." && pwd)"
export SHARED_DIR="$CORPORATE_PROXY_ROOT/shared"
export SERVICES_DIR="$SHARED_DIR/services"
export CONFIGS_DIR="$SHARED_DIR/configs"
