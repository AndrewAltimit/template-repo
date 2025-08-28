#!/bin/bash
# wait-for-it.sh - Wait for services to be ready before proceeding

set -e

TIMEOUT=${TIMEOUT:-30}
QUIET=${QUIET:-0}
HOSTS=""

wait_for() {
    local host=$1
    local port=$2
    local timeout=$3

    if [ $QUIET -eq 0 ]; then
        echo "Waiting for $host:$port to be ready..."
    fi

    for i in $(seq $timeout); do
        if nc -z "$host" "$port" 2>/dev/null; then
            if [ $QUIET -eq 0 ]; then
                echo "✓ $host:$port is ready"
            fi
            return 0
        fi
        sleep 1
    done

    echo "✗ Timeout waiting for $host:$port"
    return 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            HOSTS="$HOSTS $2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -q|--quiet)
            QUIET=1
            shift
            ;;
        *)
            break
            ;;
    esac
done

# Wait for all specified hosts
for host_port in $HOSTS; do
    host="${host_port%:*}"
    port="${host_port#*:}"
    wait_for "$host" "$port" "$TIMEOUT" || exit 1
done

# Execute remaining command if provided
if [[ $# -gt 0 ]]; then
    exec "$@"
fi
