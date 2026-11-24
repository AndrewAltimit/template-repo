#!/usr/bin/env bash
# Start, stop or check the local AWS Emulator used for offline end-to-end tests.
#
#   scripts/emulator.sh start    build the image if needed, start it, save its CA
#   scripts/emulator.sh status   health check
#   scripts/emulator.sh stop     stop it (all emulated resources are discarded)
#
# The emulator listens on 127.0.0.1 only, with request authentication off.
# State is in memory: stopping it deletes everything that was created.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

cmd="${1:-status}"
case "$cmd" in
  start)
    ensure_image "$EMU_IMAGE" aws-emulator emulator
    if emulator_running; then
      log "emulator already running"
    else
      docker rm -f "$EMU_NAME" >/dev/null 2>&1 || true
      docker run -d --name "$EMU_NAME" --memory=2g --memory-swap=2g \
        -p "127.0.0.1:$EMU_PORT:$EMU_PORT" "$EMU_IMAGE" -p "$EMU_PORT" --auth off >/dev/null
    fi
    mkdir -p "$EMU_DIR"
    for _ in $(seq 1 60); do
      if docker exec "$EMU_NAME" sh -c \
        "curl -sf --cacert /home/emulator/.aws/emulator/$EMU_PORT/ca.pem https://127.0.0.1:$EMU_PORT/__admin/health" \
        >/dev/null 2>&1; then
        docker exec "$EMU_NAME" cat "/home/emulator/.aws/emulator/$EMU_PORT/ca.pem" > "$EMU_DIR/ca.pem"
        log "emulator healthy on https://127.0.0.1:$EMU_PORT ($(docker exec "$EMU_NAME" aws-emulator -v | head -1))"
        exit 0
      fi
      sleep 1
    done
    docker logs "$EMU_NAME" | tail -20 >&2
    die "emulator did not become healthy"
    ;;
  status)
    if emulator_running; then
      docker exec "$EMU_NAME" sh -c \
        "curl -sf --cacert /home/emulator/.aws/emulator/$EMU_PORT/ca.pem https://127.0.0.1:$EMU_PORT/__admin/health" \
        && echo
    else
      echo "not running"
      exit 1
    fi
    ;;
  stop)
    docker rm -f "$EMU_NAME" >/dev/null 2>&1 || true
    find "$RDS_DIR/.emulator-state" -type f -delete 2>/dev/null || true
    log "emulator stopped; emulated resources and local emulator state discarded"
    ;;
  *)
    die "usage: emulator.sh start|status|stop"
    ;;
esac
