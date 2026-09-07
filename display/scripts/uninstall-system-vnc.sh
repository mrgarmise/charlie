#!/bin/sh
set -eu

DROPIN_DIR="/etc/systemd/system/wayvnc.service.d"
SYSTEM_PREFIX="/opt/charlie-wayvnc"

printf '%s\n' '[charlie-display] reverting Raspberry Pi admin VNC to packaged service behavior'
sudo rm -f "$DROPIN_DIR/override.conf"
sudo systemctl daemon-reload
sudo systemctl restart wayvnc.service
printf '%s\n' '[charlie-display] systemd override removed; /opt/charlie-wayvnc retained for inspection/reuse'
printf '%s\n' "[charlie-display] remove $SYSTEM_PREFIX manually only if no longer needed"
