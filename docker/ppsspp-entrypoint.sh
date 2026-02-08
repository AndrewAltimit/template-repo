#!/bin/bash
# PPSSPP entrypoint -- selects headless vs GUI mode.
#
# Environment variables:
#   PPSSPP_HEADLESS=1  -- use PPSSPPHeadless (no display required)
#   PPSSPP_HEADLESS=0  -- use PPSSPPSDL (default, needs X11)

set -e

if [ "${PPSSPP_HEADLESS}" = "1" ]; then
    exec PPSSPPHeadless "$@"
else
    exec PPSSPPSDL "$@"
fi
