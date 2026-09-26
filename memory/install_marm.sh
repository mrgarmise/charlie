#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Installing/upgrading MARM for Charlie..."
python3 -m pip install --user --upgrade marm-mcp-server

# Locate user-installed CLI even when ~/.local/bin is not yet on PATH.
export PATH="$HOME/.local/bin:$PATH"

command -v marm-memory >/dev/null || {
  echo "marm-memory was installed but is not on PATH." >&2
  echo 'Add: export PATH="$HOME/.local/bin:$PATH"' >&2
  exit 1
}

echo "Checking MARM..."
marm-memory doctor

echo "Indexing Charlie codebase..."
marm-memory projects index "$REPO_ROOT"

cat <<'EOF'

Charlie durable memory is installed and the repository is indexed.

Single local agent:
  codex mcp add marm-memory-stdio -- marm-mcp-stdio

Shared local memory for multiple agents:
  marm-memory start --profile swarm
  codex mcp add marm-memory --url http://localhost:8001/mcp

Useful checks:
  marm-memory status
  marm-memory projects status
  marm-memory console

Memory data remains in ~/.marm and is not committed to Charlie.
EOF
