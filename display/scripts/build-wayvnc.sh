#!/bin/sh
set -eu

WAYVNC_VERSION="v0.10.1"
NEATVNC_VERSION="v1.0.1"
AML_VERSION="v1.0.0"
BUILD_ROOT="${XDG_CACHE_HOME:-$HOME/.cache}/charlie-display-fabric/src"
PREFIX="${CHARLIE_WAYVNC_PREFIX:-$HOME/.local/charlie-wayvnc}"

log() { printf '%s\n' "[charlie-display] $*"; }

for cmd in git meson ninja pkg-config cc; do
    command -v "$cmd" >/dev/null 2>&1 || {
        printf 'Missing build command: %s\n' "$cmd" >&2
        exit 1
    }
done

mkdir -p "$BUILD_ROOT"
rm -rf "$BUILD_ROOT/wayvnc" "$BUILD_ROOT/neatvnc" "$BUILD_ROOT/aml"

log "cloning WayVNC $WAYVNC_VERSION"
git clone --branch "$WAYVNC_VERSION" --depth 1 https://github.com/any1/wayvnc.git "$BUILD_ROOT/wayvnc"
git clone --branch "$NEATVNC_VERSION" --depth 1 https://github.com/any1/neatvnc.git "$BUILD_ROOT/neatvnc"
git clone --branch "$AML_VERSION" --depth 1 https://github.com/any1/aml.git "$BUILD_ROOT/aml"

mkdir -p "$BUILD_ROOT/wayvnc/subprojects" "$BUILD_ROOT/neatvnc/subprojects"
ln -s "$BUILD_ROOT/neatvnc" "$BUILD_ROOT/wayvnc/subprojects/neatvnc"
ln -s "$BUILD_ROOT/aml" "$BUILD_ROOT/wayvnc/subprojects/aml"
ln -s "$BUILD_ROOT/aml" "$BUILD_ROOT/neatvnc/subprojects/aml"

meson setup "$BUILD_ROOT/wayvnc/build" "$BUILD_ROOT/wayvnc" \
    --buildtype=release \
    --prefix="$PREFIX"
ninja -C "$BUILD_ROOT/wayvnc/build"
ninja -C "$BUILD_ROOT/wayvnc/build" install

LIBDIR="$(find "$PREFIX/lib" -type f -name 'libaml.so.*' -printf '%h\n' 2>/dev/null | head -n 1)"
[ -n "$LIBDIR" ] || { printf 'Could not locate installed Charlie WayVNC libraries.\n' >&2; exit 1; }

log "installed Charlie WayVNC to $PREFIX"
LD_LIBRARY_PATH="$LIBDIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    "$PREFIX/bin/wayvnc" --version
