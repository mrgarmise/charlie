"""Offline command boundaries, with synthetic empty journals only."""
from pathlib import Path
import subprocess
import sys

from memory.evidence import EvidenceJournal


TOOL = Path(__file__).resolve().parents[1] / 'tools/recover_tactical_feedback.py'


def test_documented_direct_command_runs_outside_checkout(tmp_path):
    source = tmp_path / 'episode' / 'session.sqlite3'
    source.parent.mkdir()
    EvidenceJournal(source).close()
    before = source.read_bytes()
    result = subprocess.run([sys.executable, str(TOOL), '--journal', str(source)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '"physical_actions": 0' in result.stdout
    assert source.read_bytes() == before


def test_report_cannot_overwrite_retained_ledger(tmp_path):
    source = tmp_path / 'episode' / 'session.sqlite3'
    source.parent.mkdir()
    EvidenceJournal(source).close()
    ledger = tmp_path / 'ledger.json'
    ledger.write_text('preserve these bytes')
    result = subprocess.run([sys.executable, str(TOOL), '--journal', str(source),
                             '--write-ledger', str(ledger), '--report', str(ledger)],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'separate files' in result.stderr
    assert ledger.read_text() == 'preserve these bytes'
