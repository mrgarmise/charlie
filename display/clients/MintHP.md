# MintHP

## Admin / rescue

Keep TigerVNC configured for Charlie's Raspberry Pi OS endpoint on port 5900. This is the known-good control path and is intentionally independent of the Display Fabric.

## Charlie displays

Remmina is verified against Charlie's isolated WayVNC 0.10.1 endpoint.

- MAIN: `raspberrypi.local:5901`
- OPS: `raspberrypi.local:5902`
- FACE: `raspberrypi.local:5903`

Enable Remmina client-side scaling / fit-to-window. Do not enable remote/dynamic resolution resizing; Charlie owns the output geometry.

Credentials come from Charlie's private `~/.config/charlie-display-fabric/wayvnc.conf` and are not stored in Git.
