#!/bin/sh
set -eu

. /etc/default/keyboard

export XDG_RUNTIME_DIR=/tmp/wayvnc
mkdir -p "$XDG_RUNTIME_DIR"

export XKB_DEFAULT_MODEL="$XKBMODEL"
export XKB_DEFAULT_LAYOUT="$XKBLAYOUT"
export PATH=/opt/charlie-wayvnc/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export LD_LIBRARY_PATH=/opt/charlie-wayvnc/lib

SELF_PID=$$

{
    while ! /opt/charlie-wayvnc/bin/wayvncctl \
        --socket=/tmp/wayvnc/wayvncctl.sock \
        version >/dev/null 2>&1
    do
        sleep 0.1
    done
    systemd-notify --ready --pid="$SELF_PID"
} &

if ! raspi-config nonint is_pifive ; then
    export WAYVNC_CMA=/dev/dma_heap/linux,cma
fi

exec /opt/charlie-wayvnc/bin/wayvnc \
    --detached \
    --gpu \
    --output CHARLIE-MAIN \
    --config /etc/wayvnc/config \
    --socket /tmp/wayvnc/wayvncctl.sock
