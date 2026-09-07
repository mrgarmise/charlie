# Charlie Display Fabric — v3.1

Charlie owns a stable multi-output Wayland desktop. Remote devices choose a Charlie output and scale it locally; clients do not redefine Charlie's monitor geometry.

## Architecture

Remote access is deliberately split into an admin/rescue path and Charlie-owned display endpoints:

- `:5900` → `CHARLIE-MAIN` — Raspberry Pi OS VNC service, using tested upstream WayVNC 0.10.1 through a reversible systemd override; intended for TigerVNC admin/rescue
- `:5901` → `CHARLIE-MAIN` — 1920×1080 — general desktop
- `:5902` → `CHARLIE-OPS` — 1920×1080 — vision / telemetry / diagnostics
- `:5903` → `CHARLIE-FACE` — 800×600 — embodiment / RP2040 semantic mirror

The Charlie-owned endpoints pass `--disable-resizing`. Client applications should use local scaling / fit-to-window.

## Why Charlie uses WayVNC 0.10.1

Raspberry Pi OS 13 (trixie) currently supplies WayVNC `0.9.1-1+rpt5`. On Charlie's labwc headless outputs that build reports output power-state failures and can produce a gray VNC framebuffer. Upstream WayVNC 0.10.1 contains the fix `output: Treat failed power state as ON`; this was verified on Charlie.

The tested upstream runtime is first built under `~/.local/charlie-wayvnc`. Charlie's endpoints use that private runtime directly. For the Raspberry Pi OS admin VNC service, the same tested runtime is copied to `/opt/charlie-wayvnc` so the system `vnc` account can execute it without weakening permissions on `/home/five`.

Raspberry Pi package files remain untouched. In particular, Charlie does not overwrite:

- `/usr/bin/wayvnc`
- `/usr/sbin/wayvnc-run.sh`
- `/etc/wayvnc/config`

The admin path is customized only with a systemd drop-in and a Charlie-owned runner that explicitly binds `:5900` to `CHARLIE-MAIN` at server startup.

## Repository vs runtime state

Committed:

- topology and roles (`profiles.json`)
- labwc user configuration
- launch/status scripts
- reproducible WayVNC build script
- system-VNC runner and systemd override template
- installers/uninstaller
- client notes

Not committed:

- WayVNC source/build trees
- installed binaries/libraries under `~/.local` or `/opt`
- VNC username/password
- Raspberry Pi generated VNC keys
- runtime logs, sockets, and PID files

Private Charlie endpoint credentials live at:

```text
~/.config/charlie-display-fabric/wayvnc.conf
```

## Disaster recovery / fresh Pi setup

After cloning the Charlie repository and enabling Raspberry Pi OS VNC normally, install the required build dependencies and run:

```bash
cd ~/Projects/charlie
chmod +x display/scripts/*.sh
display/scripts/build-wayvnc.sh
display/scripts/setup-vnc-auth.sh
display/scripts/install-labwc.sh
```

Restart the graphical session or reboot so `CHARLIE-MAIN`, `CHARLIE-OPS`, and `CHARLIE-FACE` exist. Then install the tested admin/rescue VNC runtime:

```bash
display/scripts/install-system-vnc.sh
```

Reboot and verify:

```bash
display/scripts/display-status.sh
```

Expected mapping:

```text
5900 → CHARLIE-MAIN  (TigerVNC admin/rescue)
5901 → CHARLIE-MAIN  (Remmina)
5902 → CHARLIE-OPS   (Remmina)
5903 → CHARLIE-FACE  (Remmina)
```

## Reverting the :5900 customization

```bash
display/scripts/uninstall-system-vnc.sh
```

This removes the systemd drop-in and restarts Raspberry Pi OS's WayVNC service using its packaged runner again. `/opt/charlie-wayvnc` is intentionally retained so rollback does not destroy diagnostic/recovery material.

## Security

The current Charlie endpoint configuration uses `relax_encryption=true` for tested Remmina compatibility. Treat ports 5901–5903 as trusted-LAN endpoints until transport hardening is added. Do not expose them directly to the public Internet.

Port 5900 retains Raspberry Pi OS's existing `/etc/wayvnc/config`, PAM/TLS configuration, and system service identity.

## Status and control

```bash
display/scripts/display-status.sh
display/scripts/start-wayvnc-endpoints.sh
display/scripts/stop-wayvnc-endpoints.sh
```

Stopping Charlie endpoints does not stop Raspberry Pi OS VNC on port 5900 and does not remove virtual outputs.

## Recovery bindings

The Ctrl+Alt bindings remain available as recovery/testing controls:

- Ctrl+Alt+V — add MAIN
- Ctrl+Alt+B — add OPS
- Ctrl+Alt+N — add FACE

Dynamically adding/removing outputs while clients are connected can disturb input mapping. Normal operation creates outputs at graphical-session startup.
