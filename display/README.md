# Charlie Display Fabric — v3

Charlie owns a stable multi-output Wayland desktop. Remote devices choose a Charlie output and scale it locally; clients do not redefine Charlie's monitor geometry.

## Architecture

Raspberry Pi OS administration remains deliberately separate:

- `:5900` — Raspberry Pi OS system WayVNC 0.9.1+rpt5 — admin/rescue path — **do not modify**

Charlie-owned display endpoints use an isolated upstream WayVNC runtime:

- `:5901` → `CHARLIE-MAIN` — 1920×1080 — general desktop
- `:5902` → `CHARLIE-OPS` — 1920×1080 — vision / telemetry / diagnostics
- `:5903` → `CHARLIE-FACE` — 800×600 — embodiment / RP2040 semantic mirror

All Charlie endpoints pass `--disable-resizing`. Client applications should use local scaling / fit-to-window.

## Why Charlie uses WayVNC 0.10.1

Raspberry Pi OS currently supplies WayVNC 0.9.1+rpt5. On Charlie's labwc headless outputs that build reports `Power:UNKNOWN`, waits for an output power event, and produces a gray VNC framebuffer. Upstream WayVNC 0.10.1 includes `output: Treat failed power state as ON`; this was verified on Charlie with Remmina against `CHARLIE-MAIN`.

The upstream runtime is installed under `~/.local/charlie-wayvnc`. It does not replace `/usr/bin/wayvnc` or modify `/etc/wayvnc`.

## Repository vs runtime state

Committed:

- topology and roles (`profiles.json`)
- labwc user configuration
- launch/status scripts
- reproducible WayVNC build script
- client notes

Not committed:

- WayVNC source/build trees
- installed WayVNC binaries/libraries
- VNC username/password
- runtime logs and sockets

Private configuration is stored at:

```text
~/.config/charlie-display-fabric/wayvnc.conf
```

## One-time runtime setup

Install the build dependencies documented for the Pi, then build Charlie's isolated runtime:

```bash
display/scripts/build-wayvnc.sh
```

Create private credentials:

```bash
display/scripts/setup-vnc-auth.sh
```

The currently tested Remmina-compatible configuration uses `relax_encryption=true`. Treat ports 5901-5903 as trusted-LAN endpoints until transport hardening is added. Do not expose them directly to the public Internet.

## Install labwc integration

```bash
chmod +x display/scripts/*.sh
display/scripts/install-labwc.sh
```

Restart the graphical session or reboot after changing the labwc topology configuration.

At startup Charlie creates the three named virtual outputs, applies fixed geometry, then launches one isolated WayVNC 0.10.1 process per output.

## Status

```bash
display/scripts/display-status.sh
```

## Manual endpoint control

```bash
display/scripts/start-wayvnc-endpoints.sh
display/scripts/stop-wayvnc-endpoints.sh
```

Stopping Charlie endpoints does not stop Raspberry Pi OS VNC on port 5900 and does not remove the virtual outputs.

## Recovery bindings

The Ctrl+Alt bindings remain available as recovery/testing controls:

- Ctrl+Alt+V — add MAIN
- Ctrl+Alt+B — add OPS
- Ctrl+Alt+N — add FACE

Dynamically adding/removing outputs while clients are connected can disturb input mapping. Normal operation creates outputs at graphical-session startup.
