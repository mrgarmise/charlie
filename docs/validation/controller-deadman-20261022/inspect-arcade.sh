#!/bin/bash
# Read only. Run over password-authenticated SSH from an ordinary terminal.
set -euo pipefail
filter() {
    if command -v rg >/dev/null; then rg "$1"; else grep -E "$1"; fi
}
hostname
uname -a
date -u --iso-8601=seconds
cat /proc/sys/kernel/random/boot_id
systemctl cat charlie-arcade.service
systemctl show charlie-arcade.service -p MainPID -p ActiveState -p SubState -p ExecStart -p FragmentPath -p DropInPaths -p Restart -p RestartUSec -p KillMode
ps -eo pid,ppid,user,lstart,args | filter 'launcher.py|retroarch|PID' || true
ss -tnlp | filter ':8765|State' || true
git -C /home/five/arcade rev-parse HEAD 2>/dev/null || true
git -C /home/five/arcade status --short 2>/dev/null || true
python3 - <<'PY'
import hashlib
from pathlib import Path
for name in ('launcher.py', 'controller.py', 'controller_lease.py', 'rom_intake.py', 'display_control.py'):
    p = Path('/home/five/arcade') / name
    print('\nSOURCE', p, 'symlink=', p.is_symlink())
    if p.is_file():
        data = p.read_bytes()
        print('SHA256', hashlib.sha256(data).hexdigest())
        if name in ('launcher.py', 'controller.py', 'controller_lease.py'):
            print(data.decode('utf8'))
print('\nINPUT DEVICES')
print(Path('/proc/bus/input/devices').read_text())
PY
