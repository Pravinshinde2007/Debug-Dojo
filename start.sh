#!/usr/bin/env bash
# Root delegation wrapper
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$SCRIPT_DIR/debug-dojo" ]; then
    exec "$SCRIPT_DIR/debug-dojo/start.sh" "$@"
fi
