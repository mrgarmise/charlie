import hashlib
import sqlite3
import subprocess
from pathlib import Path

import pytest

from tools.discovery_release.preflight import inventory


def test_inventory_preserves_controls_and_reports_revision_mismatch(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    ops = tmp_path / "ops"
    ops.mkdir()
    pin = "a" * 40
    for name in ("QUALIFICATION.md", "start-stationary.sh", "run-historical-consultation.py", "approved.sha"):
        (ops / name).write_text(pin if name == "approved.sha" else "unchanged")
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ops.iterdir()}
    report = inventory(repo, ops, tmp_path, pin, pin)
    assert report["candidate"] == subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    assert report["control_hashes"] == before
    assert report["approved_pin"] == pin
    assert "candidate identity differs from release" in report["comparison_blockers"]
    assert report["admission_issued"] is False
    assert report["sqlite"] == sqlite3.sqlite_version
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ops.iterdir()}
    with pytest.raises(ValueError):
        inventory(repo, ops, tmp_path, "HEAD", pin)


def test_snapshot_and_restore_keep_committed_wal_and_refuse_overwrite(tmp_path):
    from learning.discovery.journal import Journal
    from tools.discovery_release.notebook_copy import verified_copy

    live, snapshot, restored = [tmp_path / name for name in ("live", "snapshot", "restored")]
    with Journal(live) as journal:
        qid = journal.queue("How does a gear ratio change speed?", owner=True)
        receipt = verified_copy(live, snapshot)
        assert receipt["sha256"] == hashlib.sha256(snapshot.read_bytes()).hexdigest()
        journal.queue("How are months defined?", owner=True)
        with pytest.raises(FileExistsError):
            verified_copy(live, snapshot)
    verified_copy(snapshot, restored)
    with Journal(restored, read_only=True) as journal:
        assert journal.select()["id"] == qid
        assert journal.db.execute("SELECT count(*) FROM questions").fetchone()[0] == 1
