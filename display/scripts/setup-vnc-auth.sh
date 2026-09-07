#!/bin/sh
set -eu

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/charlie-display-fabric"
CONFIG="$CONFIG_DIR/wayvnc.conf"
DEFAULT_USER="$(id -un)"

printf 'Charlie Display Fabric VNC username [%s]: ' "$DEFAULT_USER"
IFS= read -r USERNAME
USERNAME=${USERNAME:-$DEFAULT_USER}

printf 'Charlie Display Fabric VNC password: '
stty -echo
trap 'stty echo' EXIT HUP INT TERM
IFS= read -r PASSWORD
stty echo
printf '\n'
trap - EXIT HUP INT TERM

[ -n "$PASSWORD" ] || { printf 'Password may not be empty.\n' >&2; exit 1; }

mkdir -p "$CONFIG_DIR"
umask 077
cat > "$CONFIG" <<EOF_CONFIG
use_relative_paths=false
address=0.0.0.0
enable_auth=true
username=$USERNAME
password=$PASSWORD
relax_encryption=true
EOF_CONFIG
chmod 600 "$CONFIG"

printf 'Created private runtime config:\n  %s\n' "$CONFIG"
printf '%s\n' 'This file is outside the Git repository and must not be committed.'
printf '%s\n' 'relax_encryption=true is currently required for tested Remmina compatibility; use only on a trusted LAN until transport hardening is added.'
