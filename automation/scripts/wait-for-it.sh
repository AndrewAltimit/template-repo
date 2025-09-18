#!/usr/bin/env bash
# wait-for-it.sh: Wait for a service to be available before continuing
# Based on https://github.com/vishnubob/wait-for-it

set -e

# Default values
TIMEOUT=15
QUIET=0
WAIT_HOST=""
WAIT_PORT=""
HEALTH_ENDPOINT=""
PROTOCOL="tcp"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--host)
      WAIT_HOST="$2"
      shift 2
      ;;
    -p|--port)
      WAIT_PORT="$2"
      shift 2
      ;;
    -t|--timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    -e|--health-endpoint)
      HEALTH_ENDPOINT="$2"
      PROTOCOL="http"
      shift 2
      ;;
    -q|--quiet)
      QUIET=1
      shift
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  -h, --host HOST           Host to check (default: localhost)"
      echo "  -p, --port PORT           Port to check"
      echo "  -t, --timeout SECONDS     Timeout in seconds (default: 15)"
      echo "  -e, --health-endpoint PATH  Health check endpoint (implies HTTP check)"
      echo "  -q, --quiet               Suppress output"
      echo ""
      echo "Examples:"
      echo "  $0 --host localhost --port 8021 --timeout 30"
      echo "  $0 --host localhost --port 8021 --health-endpoint /health"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Set defaults
WAIT_HOST="${WAIT_HOST:-localhost}"

# Validate required parameters
if [[ -z "$WAIT_PORT" ]]; then
  echo "Error: Port is required"
  exit 1
fi

# Function to log messages
log() {
  if [[ $QUIET -eq 0 ]]; then
    echo "$@"
  fi
}

# Function to check TCP port
check_tcp() {
  nc -z "$WAIT_HOST" "$WAIT_PORT" > /dev/null 2>&1
}

# Function to check HTTP endpoint
check_http() {
  local url="http://${WAIT_HOST}:${WAIT_PORT}${HEALTH_ENDPOINT}"
  curl -f -s -o /dev/null "$url" 2>/dev/null
}

# Main waiting logic
log "wait-for-it.sh: waiting $TIMEOUT seconds for $WAIT_HOST:$WAIT_PORT"

start_ts=$(date +%s)
end_ts=$((start_ts + TIMEOUT))

while :; do
  if [[ "$PROTOCOL" == "http" ]] && [[ -n "$HEALTH_ENDPOINT" ]]; then
    if check_http; then
      log "wait-for-it.sh: $WAIT_HOST:$WAIT_PORT$HEALTH_ENDPOINT is available after $(($(date +%s) - start_ts)) seconds"
      break
    fi
  else
    if check_tcp; then
      log "wait-for-it.sh: $WAIT_HOST:$WAIT_PORT is available after $(($(date +%s) - start_ts)) seconds"
      break
    fi
  fi

  now_ts=$(date +%s)
  if [[ $now_ts -ge $end_ts ]]; then
    log "wait-for-it.sh: timeout occurred after waiting $TIMEOUT seconds for $WAIT_HOST:$WAIT_PORT"
    exit 1
  fi

  sleep 1
done

exit 0
