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

# Auto-detect container runtime (Docker or Podman)
detect_container_runtime() {
    if command -v docker &> /dev/null && docker info &> /dev/null 2>&1; then
        export CONTAINER_RUNTIME="docker"

        # Prefer modern 'docker compose' over legacy 'docker-compose'
        if docker compose version &> /dev/null 2>&1; then
            export COMPOSE_RUNTIME="docker compose"
        elif command -v docker compose &> /dev/null; then
            export COMPOSE_RUNTIME="docker-compose"
            print_warn "Using legacy docker-compose. Consider upgrading to Docker Compose V2."
        else
            print_error "No Docker Compose command available"
            exit 1
        fi
    elif command -v podman &> /dev/null && podman info &> /dev/null 2>&1; then
        export CONTAINER_RUNTIME="podman"
        export COMPOSE_RUNTIME="podman-compose"
    else
        print_error "Neither Docker nor Podman is available or running"
        exit 1
    fi

    print_info "Using container runtime: $CONTAINER_RUNTIME"
    print_info "Using compose runtime: $COMPOSE_RUNTIME"
}

# Check if Docker is available (backward compatibility)
check_docker() {
    detect_container_runtime
    if [ "$CONTAINER_RUNTIME" = "" ]; then
        print_error "Container runtime is not available"
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

    for _ in $(seq 1 "$max_attempts"); do
        if curl -fsS "$url" > /dev/null; then
            print_info "✓ $service_name is ready"
            return 0
        fi
        sleep 1
    done

    print_error "$service_name failed to start after $max_attempts seconds"
    return 1
}

# Build container image if not exists (works with Docker and Podman)
build_if_needed() {
    local image_name=$1
    local dockerfile=$2
    local build_context=${3:-.}
    local runtime="${CONTAINER_RUNTIME:-docker}"

    if ! $runtime image inspect "$image_name" >/dev/null 2>&1; then
        print_info "Image $image_name not found. Building..."
        if ! $runtime build --pull -f "$dockerfile" -t "$image_name" "$build_context"; then
            print_error "Failed to build $image_name"
            exit 1
        fi
        print_info "Successfully built $image_name"
    else
        print_info "Using existing image $image_name"
    fi
}

# Stop and remove container if exists (works with Docker and Podman)
cleanup_container() {
    local container_name=$1
    local runtime="${CONTAINER_RUNTIME:-docker}"

    if $runtime ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        print_info "Stopping existing container $container_name..."
        $runtime stop "$container_name" >/dev/null 2>&1
        $runtime rm "$container_name" >/dev/null 2>&1
    fi
}

# Get the script's directory (works with symlinks)
get_script_dir() {
    local source="${BASH_SOURCE[0]}"
    while [ -h "$source" ]; do
        local dir
        dir="$( cd -P "$( dirname "$source" )" && pwd )"
        source="$(readlink "$source")"
        [[ $source != /* ]] && source="$dir/$source"
    done
    cd -P "$( dirname "$source" )" && pwd
}

# Auto-detect architecture and map to Docker/Podman format
detect_architecture() {
    if [ -z "$TARGETARCH" ]; then
        local ARCH
        ARCH=$(uname -m)
        case $ARCH in
            x86_64)
                export TARGETARCH="amd64"
                ;;
            aarch64|arm64)
                export TARGETARCH="arm64"
                ;;
            armv7l)
                export TARGETARCH="arm"
                ;;
            ppc64le)
                export TARGETARCH="ppc64le"
                ;;
            s390x)
                export TARGETARCH="s390x"
                ;;
            *)
                print_warn "Unknown architecture: $ARCH, defaulting to amd64"
                export TARGETARCH="amd64"
                ;;
        esac
    fi
    print_info "Target architecture: $TARGETARCH"
}

# Check if buildx is available for multi-platform builds
check_buildx() {
    if [ "$CONTAINER_RUNTIME" = "docker" ]; then
        if docker buildx version &> /dev/null; then
            print_info "Docker buildx available for multi-arch support"
            export USE_BUILDX="true"
            export BUILD_CMD="docker buildx build --load"

            # Ensure buildx builder is available
            if ! docker buildx ls | grep -q "default.*running"; then
                print_info "Creating buildx builder..."
                docker buildx create --use --name multiarch-builder || \
                docker buildx use multiarch-builder || true
            fi
        else
            print_info "Docker buildx not available, using standard build"
            export USE_BUILDX="false"
            export BUILD_CMD="docker build"
        fi
    elif [ "$CONTAINER_RUNTIME" = "podman" ]; then
        # Podman has built-in multi-arch support
        export USE_BUILDX="false"
        export BUILD_CMD="podman build"
        print_info "Using Podman with built-in multi-arch support"
    fi
}

# Wrapper for container commands that works with both Docker and Podman
container_run() {
    $CONTAINER_RUNTIME run "$@"
}

container_build() {
    if [ "$USE_BUILDX" = "true" ]; then
        docker buildx build --load "$@"
    else
        $CONTAINER_RUNTIME build "$@"
    fi
}

container_exec() {
    $CONTAINER_RUNTIME exec "$@"
}

compose_run() {
    $COMPOSE_RUNTIME run "$@"
}

compose_build() {
    $COMPOSE_RUNTIME build "$@"
}

compose_up() {
    $COMPOSE_RUNTIME up "$@"
}

compose_down() {
    $COMPOSE_RUNTIME down "$@"
}

# Export common paths
CORPORATE_PROXY_ROOT="$(cd "$(get_script_dir)/../.." && pwd)"
export CORPORATE_PROXY_ROOT
export SHARED_DIR="$CORPORATE_PROXY_ROOT/shared"
export SERVICES_DIR="$SHARED_DIR/services"
export CONFIGS_DIR="$SHARED_DIR/configs"
