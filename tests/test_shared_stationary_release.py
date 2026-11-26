"""Isolated launcher rehearsal. No operational path or device access."""
import hashlib
from pathlib import Path
import pytest

from tools.runtime_adoption import shared_release as r


def test_switch_and_standalone_controller_rollback(tmp_path, monkeypatch):
    ctl = r.SharedRelease(tmp_path)
    ctl.ops.mkdir()
    (ctl.ops / 'logs').mkdir()
    ctl.fallback.parent.mkdir(parents=True)
    old = b'#!/bin/sh\nexit 11\n'
    ctl.normal.write_bytes(old)
    ctl.fallback.write_bytes(old)
    before = hashlib.sha256(old).hexdigest()
    monkeypatch.setattr(r.s, 'ORIGINAL', before)
    proposed = ctl.launcher()
    assert b' -IB tools/shared_stationary_ctl.py launch' in proposed
    ctl.transition(before, proposed)
    assert ctl.normal.read_bytes() == proposed
    ctl.rollback()
    assert ctl.normal.read_bytes() == old
    assert len(list((ctl.ops / 'logs').glob('shared-switch-*'))) == 2
    ctl.normal.write_text('unknown change')
    with pytest.raises(ValueError):
        ctl.rollback()
    assert ctl.normal.read_text() == 'unknown change'


def test_signed_scope_rejects_historical_candidate_and_missing_native(tmp_path):
    ctl = r.SharedRelease(tmp_path)
    with pytest.raises(ValueError):
        ctl.check_manifest(dict(candidate=r.s.CANDIDATE, baseline=r.s.BASELINE), {r.SHARED})
    assert ctl.candidate != r.s.CANDIDATE and set(ctl.scopes) == {r.SHARED}
