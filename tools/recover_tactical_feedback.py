"""Safely recover authentic recorded tactical feedback into a separate ledger.

Reads an immutable snapshot of an existing capture journal.  Default is
inspection only.  --write-ledger explicitly writes a distinct bounded JSON
diagnostic artifact, never the original evidence journal or a live policy.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import json
import shutil
from tempfile import TemporaryDirectory

from experiments.ppal.tactical_memory import TacticalDiagnosticMemory
from learning.tactical_recovery import qualified_motion_summary
from memory.evidence import EvidenceJournal


def file_sha(path):
    h = sha256()
    with Path(path).open("rb") as f:
        while True:
            data = f.read(1024 * 1024)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--journal", type=Path, action="append", required=True,
                   help="preserved per-game session-evidence.sqlite3, repeatable")
    p.add_argument("--write-ledger", type=Path,
                   help="opt-in destination outside the evidence tree; no physical activation")
    p.add_argument("--report", type=Path, help="optional report JSON destination")
    args = p.parse_args(argv)

    originals = [path.resolve(strict=True) for path in args.journal]
    if args.write_ledger is not None:
        destination = args.write_ledger.expanduser().resolve()
        for source in originals:
            if destination == source or source.parent in destination.parents:
                p.error("ledger destination may not be inside a source episode")
    else:
        destination = None
    if args.report is not None:
        report_path = args.report.expanduser().resolve()
        if any(report_path == s or s.parent in report_path.parents for s in originals):
            p.error("report may not overwrite original recording files")
    else:
        report_path = None

    class NoWrite:
        def record(self, *unused, **kwargs):
            raise RuntimeError("dry-run must not write any learned state")

    ledger = TacticalDiagnosticMemory(destination) if destination else NoWrite()
    reports = []
    for source in originals:
        if any(Path(str(source) + suffix).exists()
               for suffix in ("-wal", "-shm", "-journal")):
            p.error("journal has SQLite sidecars; take a quiesced atomic snapshot first: " + str(source))
        before = file_sha(source)
        with TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / "session-evidence.sqlite3"
            shutil.copy2(source, snapshot)
            if file_sha(snapshot) != before or file_sha(source) != before:
                raise RuntimeError("original changed during snapshot: " + str(source))
            journal = EvidenceJournal(snapshot, read_only=True)
            try:
                result = qualified_motion_summary(journal, ledger, commit=bool(destination))
            finally:
                journal.close()
        if file_sha(source) != before:
            raise RuntimeError("original evidence changed after inspection: " + str(source))
        reports.append(dict(source=str(source), source_sha256=before, **result))
    result = dict(schema="ala2-tactical-recovery-report-v1",
                  reports=reports, committed=bool(destination),
                  learned_policy_activated=False,
                  physical_actions=0,
                  independent_gameplay_and_p1_qualification="NOT YET DEMONSTRATED")
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
