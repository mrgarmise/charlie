#!/bin/sh
set -eu

PREFIX="${CHARLIE_WAYVNC_PREFIX:-$HOME/.local/charlie-wayvnc}"
WAYVNCCTL="$PREFIX/bin/wayvncctl"
RUNTIME_BASE="${XDG_RUNTIME_DIR:-/tmp/charlie-$UID}/charlie-display-fabric"

LIBDIR="$(find "$PREFIX/lib" -type f -name 'libaml.so.*' -printf '%h\n' 2>/dev/null | head -n 1 || true)"
if [ -n "$LIBDIR" ]; then
    export LD_LIBRARY_PATH="$LIBDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

for slug in main ops face; do
    socket="$RUNTIME_BASE/$slug.sock"
    pidfile="$RUNTIME_BASE/$slug.pid"

    if [ -x "$WAYVNCCTL" ] && [ -S "$socket" ]; then
        "$WAYVNCCTL" --socket="$socket" wayvnc-exit >/dev/null 2>&1 || true
    fi

    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile" 2>/dev/null || true)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    fi

    rm -f "$socket" "$pidfile"
done

printf '%s\n' '[charlie-display] Charlie VNC endpoints stopped'
