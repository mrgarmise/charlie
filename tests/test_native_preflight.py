"""Synthetic diagnostic evidence only; no device access or native safety claims."""
import json
import time
from pathlib import Path

import pytest

from tools import native_preflight as preflight
from tools import native_robotron_trial as runner
from test_native_robotron_trial import review, safe


def rows(path):
    return preflight.inventory([path.parent], path.parent/'excluded')


def assemble(path, doc):
    return preflight.assemble(rows(path), doc['runtime_revision'], doc['host_boot_id'], time.time())


def test_passing_review_preserves_timestamp_hashes_and_launcher_validity(tmp_path):
    path, doc = review(tmp_path)
    checks, result = assemble(path, doc)
    assert all(c['status'] == 'PASS' for c in checks.values())
    assert result == doc
    target = tmp_path/'assembled.json'
    target.write_text(json.dumps(result))
    assert runner.verify_review(target, 'fixture-revision') == doc


@pytest.mark.parametrize('change', ['missing', 'stale', 'boot', 'revision', 'future', 'nan'])
def test_missing_and_stale_proofs_never_refresh(tmp_path, change):
    path, doc = review(tmp_path)
    current = dict(doc)
    if change == 'missing':
        del doc['proofs']['independent_physical_stop']
    elif change == 'stale':
        doc['reviewed_at'] -= 3601
    elif change == 'boot':
        doc['host_boot_id'] = 'previous-boot'
    elif change == 'revision':
        doc['runtime_revision'] = 'previous-revision'
    elif change == 'future':
        doc['reviewed_at'] += 100
    else:
        doc['reviewed_at'] = float('nan')
    path.write_text(json.dumps(doc))
    checks, result = assemble(path, current)
    assert result is None
    assert checks['independent_physical_stop']['status'] == ('NEEDS OPERATOR VERIFICATION' if change == 'missing' else 'STALE')


def test_changed_and_conflicting_evidence_fail_closed(tmp_path):
    path, doc = review(tmp_path)
    other = tmp_path/'other.txt'; other.write_text('different independently recorded fixture')
    second = json.loads(json.dumps(doc))
    second['proofs']['independent_physical_stop'] = preflight.binding(other)
    (tmp_path/'second.json').write_text(json.dumps(second))
    checks, result = assemble(path, doc)
    assert checks['independent_physical_stop']['status'] == 'FAIL'
    assert result is None
    other.write_text('changed')
    assert assemble(path, doc)[0]['independent_physical_stop']['status'] == 'FAIL'


def test_independent_parts_assemble_with_oldest_actual_review_time(tmp_path):
    path, doc = review(tmp_path)
    parts = []
    for i, (key, proof) in enumerate(doc['proofs'].items()):
        part = dict(doc, proofs={key: proof}, reviewed_at=doc['reviewed_at']-i)
        p = tmp_path/f'part{i}.json'; p.write_text(json.dumps(part)); parts.append(p)
    records = [r for r in rows(path) if r['path'] != str(path)]
    checks, result = preflight.assemble(records, doc['runtime_revision'], doc['host_boot_id'], time.time())
    assert all(v['status'] == 'PASS' for v in checks.values())
    assert result['reviewed_at'] == doc['reviewed_at']-6


def test_historical_xml_keeps_scope_and_cannot_certify_host(tmp_path):
    path, doc = review(tmp_path)
    path.unlink()
    records = rows(path)
    receipt = next(r for r in records if r['kind'] == 'test_receipt')
    assert receipt['socket_coverage'] == 'PASS'
    assert 'original scope' in receipt['qualification']
    checks, result = preflight.assemble(records, 'fixture-revision', doc['host_boot_id'], time.time())
    assert result is None
    assert all(v['status'] == 'NEEDS OPERATOR VERIFICATION' for v in checks.values())


def test_missing_lease_cases_and_suite_error_rejected(tmp_path):
    import xml.etree.ElementTree as ET
    path, doc = review(tmp_path)
    receipt = Path(doc['proofs']['software_tests']['path'])
    tree = ET.parse(receipt); suite = next(tree.iter('testsuite'))
    suite.set('errors', '1'); tree.write(receipt)
    with pytest.raises(ValueError, match='must pass'):
        runner.verify_software_receipt(receipt)
    suite.set('errors', '0')
    for case in list(suite):
        if case.get('classname') == 'tests.test_arcade_controller_lease_client':
            suite.remove(case)
    tree.write(receipt)
    with pytest.raises(ValueError, match='four controller lease'):
        runner.verify_software_receipt(receipt, require_lease=True)


def test_full_diagnostic_preserves_campaign_and_evidence(tmp_path, monkeypatch):
    from learning import campaign
    prepared = tmp_path/'campaign'; prepared.mkdir()
    state = dict(source={'revision': 'old'}, phase='ready', mode='3-meditation-3', games=6, blocks=2)
    (prepared/'campaign.json').write_text(json.dumps(state))
    (prepared/'prior-capture.bin').write_bytes(b'original campaign evidence')
    before = {p: p.read_bytes() for p in prepared.iterdir()}
    monkeypatch.setattr(preflight, 'inventory', lambda *a: [])
    monkeypatch.setattr(preflight, 'host_batch', lambda *a: dict(resources=safe(), controller_reachability={'returncode': 0}))
    monkeypatch.setattr(preflight.subprocess, 'check_output', lambda cmd, **kw: 'new\n' if 'rev-parse' in cmd else '')
    monkeypatch.setattr(campaign, 'source_identity', lambda: {'revision': 'new'})
    output = tmp_path/'audit'
    assert preflight.main(['--expected-revision', 'new', '--campaign', str(prepared), '--output', str(output)]) == 1
    report = json.loads((output/'report.json').read_text())
    assert report['checks']['campaign_source']['status'] == 'FAIL'
    assert report['review_path'] is None and report['armed'] is False
    assert {p: p.read_bytes() for p in prepared.iterdir()} == before
    with pytest.raises(FileExistsError):
        preflight.main(['--expected-revision', 'new', '--campaign', str(prepared), '--output', str(output)])


def test_controller_probe_never_opens_transport(tmp_path, monkeypatch):
    calls = []
    class Result:
        returncode=0; stdout='fixture'; stderr=''
    monkeypatch.setattr(preflight.subprocess, 'run', lambda cmd, **kw: calls.append(cmd) or Result())
    monkeypatch.setattr(runner, 'sample', lambda **kw: safe())
    result = preflight.host_batch(tmp_path, 'fixture-host')
    assert calls[-1] == ['ping', '-n', '-c', '1', '-W', '2', 'fixture-host']
    assert 'no TCP' in result['controller_scope']


def test_full_pass_writes_exact_review_without_issuing_authority(tmp_path, monkeypatch):
    from learning import campaign
    evidence = tmp_path/'evidence'; evidence.mkdir()
    path, doc = review(evidence)
    records = rows(path)
    prepared = tmp_path/'campaign'; prepared.mkdir()
    state = dict(source={'revision': 'fixture-revision'}, phase='ready', mode='3-meditation-3', games=6, blocks=2)
    (prepared/'campaign.json').write_text(json.dumps(state))
    (prepared/'authority.json').write_text('{}')
    before = {p: p.read_bytes() for p in prepared.iterdir()}
    monkeypatch.setattr(preflight, 'inventory', lambda *a: records)
    monkeypatch.setattr(preflight, 'host_batch', lambda *a: dict(resources=safe(), controller_reachability={'returncode': 0}))
    monkeypatch.setattr(preflight.subprocess, 'check_output', lambda cmd, **kw: 'fixture-revision\n' if 'rev-parse' in cmd else '')
    monkeypatch.setattr(campaign, 'source_identity', lambda: state['source'])
    monkeypatch.setattr(campaign, 'check_authority', lambda *a: None)
    real_read = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda p, *a, **kw: 'systemd\n' if str(p) == '/proc/1/comm' else real_read(p, *a, **kw))
    output = tmp_path/'audit'
    assert preflight.main(['--expected-revision', 'fixture-revision', '--campaign', str(prepared), '--output', str(output)]) == 0
    assert runner.verify_review(output/'review.json', 'fixture-revision') == doc
    assert {p: p.read_bytes() for p in prepared.iterdir()} == before


def test_malformed_xml_is_a_diagnostic_not_a_crash(tmp_path):
    path, doc = review(tmp_path)
    receipt = Path(doc['proofs']['software_tests']['path'])
    receipt.write_text('<broken')
    doc['proofs']['software_tests'] = preflight.binding(receipt)
    path.write_text(json.dumps(doc))
    checks, result = assemble(path, doc)
    assert checks['software_tests']['status'] == 'FAIL'
    assert result is None
