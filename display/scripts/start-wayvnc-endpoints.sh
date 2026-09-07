#!/bin/sh
set -eu

PREFIX="${CHARLIE_WAYVNC_PREFIX:-$HOME/.local/charlie-wayvnc}"
WAYVNC="$PREFIX/bin/wayvnc"
WAYVNCCTL="$PREFIX/bin/wayvncctl"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/charlie-display-fabric/wayvnc.conf"
RUNTIME_BASE="${XDG_RUNTIME_DIR:-/tmp/charlie-$UID}/charlie-display-fabric"
STATE_BASE="${XDG_STATE_HOME:-$HOME/.local/state}/charlie-display-fabric"

log() { printf '%s\n' "[charlie-display] $*" >&2; }

[ -x "$WAYVNC" ] || { log "Charlie WayVNC missing: $WAYVNC"; exit 1; }
[ -x "$WAYVNCCTL" ] || { log "Charlie wayvncctl missing: $WAYVNCCTL"; exit 1; }
[ -r "$CONFIG" ] || { log "private VNC config missing: $CONFIG"; exit 1; }

LIBDIR="$(find "$PREFIX/lib" -type f -name 'libaml.so.*' -printf '%h\n' 2>/dev/null | head -n 1)"
[ -n "$LIBDIR" ] || { log 'Charlie WayVNC private library directory not found'; exit 1; }
export LD_LIBRARY_PATH="$LIBDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

mkdir -p "$RUNTIME_BASE" "$STATE_BASE"
chmod 700 "$RUNTIME_BASE" "$STATE_BASE"

start_one() {
    output=$1
    port=$2
    slug=$3
    socket="$RUNTIME_BASE/$slug.sock"
    pidfile="$RUNTIME_BASE/$slug.pid"
    logfile="$STATE_BASE/$slug.log"

    if [ -S "$socket" ] && "$WAYVNCCTL" --socket="$socket" output-list >/dev/null 2>&1; then
        log "$output already serving on port $port"
        return 0
    fi

    rm -f "$socket" "$pidfile"
    nohup "$WAYVNC" \
        --disable-resizing \
        --config "$CONFIG" \
        --output "$output" \
        --socket "$socket" \
        --name "$output" \
        "0.0.0.0:$port" >>"$logfile" 2>&1 &
    pid=$!
    printf '%s\n' "$pid" > "$pidfile"

    i=0
    while [ "$i" -lt 20 ]; do
        if [ -S "$socket" ] && "$WAYVNCCTL" --socket="$socket" output-list >/dev/null 2>&1; then
            log "$output serving on port $port"
            return 0
        fi
        if ! kill -0 "$pid" 2>/dev/null; then
            log "$output failed to start; see $logfile"
            return 1
        fi
        sleep 0.1
        i=$((i + 1))
    done

    log "$output did not become ready; see $logfile"
    return 1
}

start_one CHARLIE-MAIN 5901 main
start_one CHARLIE-OPS 5902 ops
start_one CHARLIE-FACE 5903 face
