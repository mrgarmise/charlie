"""Verify, snapshot or restore a research notebook into a fresh private file."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from learning.discovery.journal import Journal


def verified_copy(source, dest):
    """SQLite's backup API includes committed WAL pages in one consistent view."""
    source, dest = Path(source), Path(dest)
    if dest.exists() or dest.is_symlink():
        raise FileExistsError(dest)
    with Journal(source, read_only=True) as journal:
        with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
            candidate = Path(tmp) / "snapshot"
            with sqlite3.connect(candidate) as backup:
                journal.db.backup(backup)
                backup.execute("PRAGMA journal_mode=DELETE")
                if backup.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise ValueError("notebook integrity check failed")
                if backup.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("inconsistent journal references")
            backup.close()
            candidate.chmod(0o600)
            with candidate.open("rb") as stream:
                os.fsync(stream.fileno())
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            # Atomic no-replace publication even if another writer races us.
            os.link(candidate, dest)
            candidate.unlink()
            parent = os.open(dest.parent, os.O_DIRECTORY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
    return dict(bytes=dest.stat().st_size, sha256=digest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("new_destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(verified_copy(args.source, args.new_destination)))
