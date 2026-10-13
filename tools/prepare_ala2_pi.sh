#!/usr/bin/env bash
# Isolate a pinned update. Never reset, stash, clean, or start gameplay.
set -euo pipefail
if [[ $# != 1 || ! $1 =~ ^[0-9a-f]{40}$ ]]; then
    echo 'Usage: bash tools/prepare_ala2_pi.sh FULL_VERIFIED_COMMIT_SHA' >&2
    exit 2
fi
ala2_target=$1
ala2_repo=$(git rev-parse --show-toplevel)
ala2_python="$ala2_repo/.venv/bin/python"
if [[ ! -x $ala2_python ]]; then
    echo 'Expected the existing Pi Python environment at .venv/bin/python.' >&2
    exit 2
fi
ala2_checkout="$HOME/charlie-ala2-${ala2_target:0:12}"
if [[ -e $ala2_checkout ]]; then
    echo "Refusing to overwrite existing checkout: $ala2_checkout" >&2
    exit 2
fi
git -C "$ala2_repo" fetch origin feature/agency-first-self
git -C "$ala2_repo" cat-file -e "$ala2_target^{commit}"
git -C "$ala2_repo" merge-base --is-ancestor d10cc2fa26bafe48375d36ac2cd70c569d3d1a18 "$ala2_target"
git -C "$ala2_repo" worktree add --detach "$ala2_checkout" "$ala2_target"
cd "$ala2_checkout"
export PYTHONPATH="$ala2_checkout"
"$ala2_python" -c "from learning.cycle import gameplay_active; assert not gameplay_active(), 'Stop active gameplay before offline validation'"
"$ala2_python" -m pytest tests -q | tee "$ala2_checkout/ala2-regression.txt"
"$ala2_python" -m learning.readiness --output "$ala2_checkout/ala2-readiness.json"
printf '\nValidated code checkout: %s\nExisting Python: %s\n' "$ala2_checkout" "$ala2_python"
printf 'Original evidence and modifications remain at: %s\nNo camera, controller, START or armed gameplay was invoked.\n' "$ala2_repo"
