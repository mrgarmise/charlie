#!/bin/bash
# Standalone recovery. Run on Charlie as five; only the canonical launcher changes.
set -euo pipefail
cd "${HOME:?}/charlie-ops"
exec 9>>runtime.lock
flock -n 9
original=promotion-backups/batch-a-20261119T220807Z/start-stationary.sh
test ! -L "$original"
sha256sum --check --status <<EOF
3305e83b84874162578d70f0de276c3dde5a80883261782bf0052db5420bd5e2  $original
5022c8cf88b0928d9abea764510d53d10ace5cc570447e7650db406b2cb70e30  approved.sha
3a3956e899c20609a25ef6d63964aa80f9ef7894cd1c93955603c5db62c62a75  run-historical-consultation.py
EOF
test "$(git -C ../charlie-runtime rev-parse HEAD)" = "$(cat approved.sha)"
test "$(git -C ../charlie-runtime rev-parse 'HEAD^{tree}')" = 72cd9e4eba5939c181ae88d6ed03d5bbc50527c4
test -z "$(git -C ../charlie-runtime status --porcelain --untracked-files=all)"
tmp=$(mktemp ./stationary-restore.XXXXXXXX)
trap 'rm -f -- "$tmp"' EXIT
install -m 700 -- "$original" "$tmp"
cmp -- "$original" "$tmp"
printf '%s restoring approved stationary launcher\n' "$(date -u +%FT%TZ)" >> logs/stationary-rollback.log
mv -Tf -- "$tmp" start-stationary.sh
