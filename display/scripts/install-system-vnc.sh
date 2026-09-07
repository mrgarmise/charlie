#!/bin/sh
set -eu

REPO="${CHARLIE_REPO:-$HOME/Projects/charlie}"
USER_PREFIX="${CHARLIE_WAYVNC_PREFIX:-$HOME/.local/charlie-wayvnc}"
SYSTEM_PREFIX="/opt/charlie-wayvnc"
DROPIN_DIR="/etc/systemd/system/wayvnc.service.d"
RUNNER_SRC="$REPO/display/system-vnc/wayvnc-run-main.sh"
OVERRIDE_SRC="$REPO/display/system-vnc/wayvnc.service.override.conf"

log() { printf '%s\n' "[charlie-display] $*"; }
fail() { printf '%s\n' "[charlie-display] ERROR: $*" >&2; exit 1; }

[ -x "$USER_PREFIX/bin/wayvnc" ] || fail "Charlie WayVNC runtime not found at $USER_PREFIX. Run display/scripts/build-wayvnc.sh first."
[ -x "$USER_PREFIX/bin/wayvncctl" ] || fail "wayvncctl missing from $USER_PREFIX/bin."
[ -f "$RUNNER_SRC" ] || fail "Missing $RUNNER_SRC"
[ -f "$OVERRIDE_SRC" ] || fail "Missing $OVERRIDE_SRC"
[ -f /etc/wayvnc/config ] || fail "Raspberry Pi OS WayVNC config /etc/wayvnc/config is missing. Enable the stock VNC service first."

LIBDIR="$(find "$USER_PREFIX/lib" -type f -name 'libaml.so.*' -printf '%h\n' 2>/dev/null | head -n 1)"
[ -n "$LIBDIR" ] || fail "Could not locate Charlie WayVNC libraries under $USER_PREFIX/lib."

VERSION="$(LD_LIBRARY_PATH="$LIBDIR" "$USER_PREFIX/bin/wayvnc" --version 2>&1 || true)"
printf '%s\n' "$VERSION" | grep -q '0\.10\.1' || fail "Expected tested WayVNC 0.10.1 runtime; got: $VERSION"

log "installing tested WayVNC runtime for Raspberry Pi admin VNC"
sudo install -d -m 0755 "$SYSTEM_PREFIX/bin" "$SYSTEM_PREFIX/lib"
sudo install -m 0755 "$USER_PREFIX/bin/wayvnc" "$SYSTEM_PREFIX/bin/wayvnc"
sudo install -m 0755 "$USER_PREFIX/bin/wayvncctl" "$SYSTEM_PREFIX/bin/wayvncctl"
sudo cp -a "$LIBDIR"/. "$SYSTEM_PREFIX/lib/"
sudo install -m 0755 "$RUNNER_SRC" "$SYSTEM_PREFIX/wayvnc-run-main.sh"

log "installing reversible systemd drop-in"
sudo install -d -m 0755 "$DROPIN_DIR"
sudo install -m 0644 "$OVERRIDE_SRC" "$DROPIN_DIR/override.conf"
sudo systemctl daemon-reload
sudo systemctl restart wayvnc.service

sleep 1
sudo systemctl is-active --quiet wayvnc.service || fail "wayvnc.service did not become active."

ACTIVE_EXE="$(sudo readlink -f "$(systemctl show -p MainPID --value wayvnc.service | sed 's#^#/proc/#; s#$#/exe#')" 2>/dev/null || true)"
# wayvnc.service MainPID is the wrapper shell under Type=notify; verify listener/process separately below.

if ! sudo ss -ltnp 2>/dev/null | grep -q ':5900.*wayvnc'; then
    fail "No WayVNC listener detected on TCP 5900."
fi

OUTPUTS="$(sudo -u vnc env \
    PATH="$SYSTEM_PREFIX/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LD_LIBRARY_PATH="$SYSTEM_PREFIX/lib" \
    "$SYSTEM_PREFIX/bin/wayvncctl" --socket=/tmp/wayvnc/wayvncctl.sock output-list 2>&1 || true)"

printf '%s\n' "$OUTPUTS"
printf '%s\n' "$OUTPUTS" | grep -q '^\* CHARLIE-MAIN:' || fail "Admin VNC is not bound to CHARLIE-MAIN. Ensure the Display Fabric outputs exist, then restart wayvnc.service."

log "Raspberry Pi admin VNC is using Charlie WayVNC 0.10.1 on :5900 and bound to CHARLIE-MAIN"
log "Raspberry Pi package files and /etc/wayvnc/config were left untouched"
