#!/bin/sh
set -u

PREFIX="${CHARLIE_WAYVNC_PREFIX:-$HOME/.local/charlie-wayvnc}"
WAYVNCCTL="$PREFIX/bin/wayvncctl"
RUNTIME_BASE="${XDG_RUNTIME_DIR:-/tmp/charlie-$UID}/charlie-display-fabric"

LIBDIR="$(find "$PREFIX/lib" -type f -name 'libaml.so.*' -printf '%h\n' 2>/dev/null | head -n 1 || true)"
if [ -n "$LIBDIR" ]; then
    export LD_LIBRARY_PATH="$LIBDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

printf '%s\n' '--- WAYLAND OUTPUTS ---'
wlr-randr 2>&1 || true

printf '\n%s\n' '--- RASPBERRY PI ADMIN VNC :5900 ---'
sudo -u vnc wayvncctl --socket=/tmp/wayvnc/wayvncctl.sock output-list 2>&1 || true

printf '\n%s\n' '--- CHARLIE DISPLAY ENDPOINTS ---'
for spec in 'main CHARLIE-MAIN 5901' 'ops CHARLIE-OPS 5902' 'face CHARLIE-FACE 5903'; do
    set -- $spec
    slug=$1 output=$2 port=$3
    socket="$RUNTIME_BASE/$slug.sock"
    printf '%s :%s\n' "$output" "$port"
    if [ -x "$WAYVNCCTL" ] && [ -S "$socket" ]; then
        "$WAYVNCCTL" --socket="$socket" output-list 2>&1 || true
    else
        printf '  not running (no control socket %s)\n' "$socket"
    fi
done

printf '\n%s\n' '--- WAYVNC PROCESSES ---'
ps -ef | grep '[w]ayvnc' || true
