#!/bin/sh
set -eu

REPO="$HOME/Projects/charlie"
LABWC_DIR="$HOME/.config/labwc"
RC="$LABWC_DIR/rc.xml"
AUTOSTART="$LABWC_DIR/autostart"
STAMP="$(date +%Y%m%d-%H%M%S)"

printf '%s\n' 'Charlie Display Fabric v3 installer'

for cmd in labwc wlr-randr wayvncctl wtype; do
    command -v "$cmd" >/dev/null 2>&1 || {
        printf 'Missing required command: %s\n' "$cmd" >&2
        exit 1
    }
done

mkdir -p "$LABWC_DIR"

if [ -f "$RC" ]; then
    cp "$RC" "$RC.before-charlie-display-fabric.$STAMP"
    printf 'Backed up rc.xml to:\n  %s\n' "$RC.before-charlie-display-fabric.$STAMP"
fi
if [ -f "$AUTOSTART" ]; then
    cp "$AUTOSTART" "$AUTOSTART.before-charlie-display-fabric.$STAMP"
    printf 'Backed up autostart to:\n  %s\n' "$AUTOSTART.before-charlie-display-fabric.$STAMP"
fi

cp "$REPO/display/labwc/rc.xml" "$RC"

HOOK="$REPO/display/scripts/start-display-fabric.sh &"
if [ -f "$AUTOSTART" ]; then
    if ! grep -Fq "$HOOK" "$AUTOSTART"; then
        printf '\n# Charlie Display Fabric\n%s\n' "$HOOK" >> "$AUTOSTART"
    fi
else
    cp "$REPO/display/labwc/autostart" "$AUTOSTART"
fi

chmod +x "$REPO/display/scripts/"*.sh

printf '%s\n' 'Installed Charlie labwc user configuration.'
printf '%s\n' 'System files under /etc/xdg/labwc and /etc/wayvnc were not modified.'
printf '%s\n' 'Charlie VNC runtime requires ~/.local/charlie-wayvnc and private auth config.'
printf '%s\n' 'A graphical session restart is required after topology configuration changes.'
