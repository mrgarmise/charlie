#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$SCRIPT_DIR/stop-wayvnc-endpoints.sh"

# Virtual outputs intentionally remain compositor-owned for the life of the
# graphical session. Removing active outputs can disturb input mapping and
# connected clients. Restart the graphical session to rebuild topology cleanly.
printf '%s\n' '[charlie-display] virtual outputs left intact'
