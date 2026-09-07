#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
log() { printf '%s\n' "[charlie-display] $*" >&2; }
has_output() { wlr-randr 2>/dev/null | grep -q "^$1 "; }

command -v wlr-randr >/dev/null 2>&1 || { log 'wlr-randr missing'; exit 1; }
command -v wtype >/dev/null 2>&1 || { log 'wtype missing; install package wtype'; exit 1; }

# Give labwc and Raspberry Pi desktop components a moment to settle.
sleep 1

# Invoke labwc-owned VirtualOutputAdd actions through local keybindings.
# Only create outputs that do not already exist.
if ! has_output CHARLIE-MAIN; then
    wtype -M ctrl -M alt -P v -m alt -m ctrl
    sleep 0.3
fi
if ! has_output CHARLIE-OPS; then
    wtype -M ctrl -M alt -P b -m alt -m ctrl
    sleep 0.3
fi
if ! has_output CHARLIE-FACE; then
    wtype -M ctrl -M alt -P n -m alt -m ctrl
    sleep 0.5
fi

# Apply Charlie-owned geometry after all outputs exist.
if has_output CHARLIE-MAIN; then
    wlr-randr --output CHARLIE-MAIN --pos 0,0 --custom-mode 1920x1080 || true
fi
if has_output CHARLIE-OPS; then
    wlr-randr --output CHARLIE-OPS --pos 1920,0 --custom-mode 1920x1080 || true
fi
if has_output CHARLIE-FACE; then
    wlr-randr --output CHARLIE-FACE --pos 3840,0 --custom-mode 800x600 || true
fi

if has_output CHARLIE-MAIN && has_output CHARLIE-OPS && has_output CHARLIE-FACE; then
    if ! "$SCRIPT_DIR/start-wayvnc-endpoints.sh"; then
        log 'topology is active, but one or more Charlie VNC endpoints failed'
        exit 1
    fi
else
    log 'one or more named outputs are missing; VNC endpoints not started'
    exit 1
fi

log 'display fabric startup complete'
