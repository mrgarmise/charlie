# Pinned ARMv6 controller lease handoff

Prepared release, not native-qualified yet. Arcade [PR #4](https://github.com/mrgarmise/charlie-arcade/pull/4):
`5ed9cc6fdf66cb22b93ba1587170e8280bc6a417`.
Charlie runtime in [PR #9](https://github.com/mrgarmise/charlie/pull/9):
`d6ef07b0b5a5959feedf50ef7f53a7fa026e29c6`.
Both descend directly from their reviewed GitHub heads. Keep these full pins.
No agent command installed, stopped, restarted or played the live arcade.

Run each block in an ordinary arcade SSH terminal as `five`. A failed command
ends that phase: retain its output and do not proceed. Git requires your normal
repository access. All checkouts and receipts are new; nothing replaces ~/arcade.

## Native device-free test (safe with the existing emulator active)

```bash
bash
set -euo pipefail
LEASE_CANDIDATE=5ed9cc6fdf66cb22b93ba1587170e8280bc6a417
CHARLIE_CLIENT=d6ef07b0b5a5959feedf50ef7f53a7fa026e29c6
LEASE_REPORT=$(mktemp -d "$HOME/controller-lease-20261022.XXXXXXXX")
export LEASE_CANDIDATE CHARLIE_CLIENT LEASE_REPORT
printf 'Keep this terminal and evidence directory: %s\n' "$LEASE_REPORT"
test "$(hostname)" = charlie-arcade
test "$(uname -m)" = armv6l
git clone --filter=blob:none --no-checkout https://github.com/mrgarmise/charlie-arcade.git "$LEASE_REPORT/arcade-source"
git -C "$LEASE_REPORT/arcade-source" checkout --detach "$LEASE_CANDIDATE"
git clone --filter=blob:none --no-checkout https://github.com/mrgarmise/charlie.git "$LEASE_REPORT/charlie-client"
git -C "$LEASE_REPORT/charlie-client" sparse-checkout set experiments/ppal
git -C "$LEASE_REPORT/charlie-client" checkout --detach "$CHARLIE_CLIENT"
cd "$LEASE_REPORT/arcade-source"
test "$(git rev-parse HEAD)" = "$LEASE_CANDIDATE"
test -z "$(git status --porcelain --untracked-files=no)"
export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=src:tests CHARLIE_TEST_ROOT="$LEASE_REPORT/charlie-client" \
  python3 -m unittest discover -s tests -v > "$LEASE_REPORT/armv6-tests.txt" 2>&1
tail -6 "$LEASE_REPORT/armv6-tests.txt"
python3 -m compileall -q -b src scripts tests
bash -n install.sh verify-install.sh
git diff --check
```

Require **256 tests, OK, no skips**. In particular the log must show
`test_frozen_real_charlie_client_releases_with_socket_still_open ... ok`.
Tests use fake controllers/emulators and synthetic ROMs, not the live TCP port or
/dev/uinput. Compileall creates only ignored/untracked bytecode in this new
checkout. Save `uname -a`, `python3 --version` and `git rev-parse HEAD` with the log.
Do not substitute the ARM64 receipt for this native result.

## Operator-controlled stop, backup and guarded install

First review the test receipt. The existing Robotron process has in-memory state;
archive backups cannot save it. Save any wanted game state yourself, then exit
the existing game using your normal physical controls. Do not select another game.
Leave the launcher at its menu. Only then execute this block in the same shell:

```bash
! pgrep -x retroarch
systemctl cat charlie-arcade.service > "$LEASE_REPORT/unit-before.txt"
systemctl show charlie-arcade.service > "$LEASE_REPORT/service-before.txt"
ps -eo pid,ppid,user,lstart,args > "$LEASE_REPORT/processes-before.txt"
cat /proc/sys/kernel/random/boot_id > "$LEASE_REPORT/boot-id.txt"
sha256sum "$HOME/arcade/launcher.py" "$HOME/arcade/controller.py" \
  "$HOME/arcade/rom_intake.py" "$HOME/arcade/display_control.py" > "$LEASE_REPORT/installed-before.sha256"
df -h "$HOME" > "$LEASE_REPORT/disk-before.txt"
# Operator has now chosen to stop the existing service.
sudo systemctl stop charlie-arcade.service
! systemctl is-active --quiet charlie-arcade.service
! pgrep -x retroarch
# Check free space first; tar must succeed completely. These retain ROMs,
# settings, saves, catalog/WAL, intake originals, sessions and user evidence.
tar -cpf "$LEASE_REPORT/home-before.tar" -C "$HOME" arcade .config/retroarch RetroArch
sudo tar -cpf "$LEASE_REPORT/systemd-before.tar" -C /etc/systemd/system \
  charlie-arcade.service charlie-arcade.service.d
tar -tf "$LEASE_REPORT/home-before.tar" > "$LEASE_REPORT/home-backup-list.txt"
sudo tar -tf "$LEASE_REPORT/systemd-before.tar" > "$LEASE_REPORT/unit-backup-list.txt"
python3 - <<'PY'
import os, sqlite3
from pathlib import Path
p = Path.home() / 'arcade/rom-intake/catalog.sqlite3'
if p.exists():
    with sqlite3.connect('file:' + str(p) + '?mode=ro', uri=True) as source:
        with sqlite3.connect(str(Path(os.environ['LEASE_REPORT']) / 'catalog-before.sqlite3')) as dest:
            source.backup(dest)
            assert dest.execute('PRAGMA integrity_check').fetchone() == ('ok',)
PY
python3 scripts/preflight_playable_library.py --expected-commit "$LEASE_CANDIDATE" > "$LEASE_REPORT/before.json"
python3 scripts/install_rom_intake.py --expected-commit "$LEASE_CANDIDATE" > "$LEASE_REPORT/install.json"
python3 scripts/preflight_playable_library.py --expected-commit "$LEASE_CANDIDATE" \
  --installed-candidate --baseline-report "$LEASE_REPORT/before.json" > "$LEASE_REPORT/after.json"
python3 - <<'PY'
import json, os
from pathlib import Path
r = Path(os.environ['LEASE_REPORT'])
i = json.loads((r / 'install.json').read_text())
assert i['persistent_evidence_preserved'] is True
assert i['service_started'] is False
assert i['protected_before']
assert Path(i['backup'], 'manifest.json').is_file()
print('Installed, service left stopped. Module rollback backup:', i['backup'])
PY
```

Do not rerun install.sh. Never relax an installer/preflight refusal. If native
library/evidence preflight refuses existing history, preserve the report and
stop; do not migrate/requalify ROMs to get past it. A partial archive is failure.
The guarded installer also backs up modules and SQLite, compares protected state
and library/history, and rolls back a failed update while retaining failure DB.

After reviewing successful receipts, operator startup is a separate step: start
the existing unit at its menu, then complete [physical neutral acceptance](README.md#5-physical-neutral-release-acceptance--not-executed).
Require independent kernel-output proof of uninterrupted renewal and release
within 1.4 s after SIGSTOP with socket open, rejection after CONT, all-client
NEUTRAL and independent physical stop. No gameplay is part of that diagnostic.

For later rollback, operator stops the service and confirms no RetroArch;
retain all new evidence. Restore only the modules named in the install backup's
`manifest.json`, preserving metadata. Remove controller_lease.py only when
`module_existed` records false. Verify restored SHA256s against the retained
original module backup/inspection. Keep the current catalog and newer history;
do not restore an old DB merely to revert code. Verify SQLite integrity and the
original unit/config hashes before operator startup. Full archives are recovery
copies, not instructions to overwrite newer user data.

## Immediately following acceptance: the two-game trial

On **Charlie**, obtain a separate clean checkout at runtime
`d6ef07b0b5a5959feedf50ef7f53a7fa026e29c6`. Use the existing
[foreground trial procedure](../experience-action-20261021/NATIVE-OPERATOR.md),
setting `CODE` to that checkout and `SHA` to this exact runtime pin. Re-run its
native socket selection there and bind a fresh same-boot review to that SHA,
including the new arcade acceptance receipt and exact server SHA. The runner
requires LEASE support; every progressing execute renews, with no supervisor
heartbeat. Run the unarmed inspection first, then its single `--run` command
for at most two games once the stated technical prerequisites pass. Existing
standing gameplay authorization applies. Preserve the complete trial output;
Game 1 completion and fresh Game 2 START require independent acceptance.
