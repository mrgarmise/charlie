"""Synthetic immutable-session retry and changed-source recovery boundaries."""
from memory.evidence import EvidenceJournal
from experiments.ppal.inspect_robotron_score import import_queue


def test_unchanged_session_retry_uses_verified_receipt(tmp_path, monkeypatch):
    root=tmp_path/'episode';root.mkdir()
    source=EvidenceJournal(root/'session-evidence.sqlite3')
    record=source.append('observation',dict(category='original'),episode='capture:one',producer='test',version='1')
    source.close()
    target=EvidenceJournal(tmp_path/'working.sqlite3')
    try:
        import_queue(target,root)
        before=[r.id for r in target.records()]
        assert record.id in before
        with monkeypatch.context() as patch:
            patch.setattr(EvidenceJournal,'verify',lambda self: (_ for _ in ()).throw(AssertionError('unchanged source reopened')))
            import_queue(target,root)
        assert [r.id for r in target.records()]==before
        # A changed source must take the ordinary verification/import path.
        source=EvidenceJournal(root/'session-evidence.sqlite3')
        extra=source.append('observation',dict(category='later'),episode='capture:one',producer='test',version='1')
        source.close()
        import_queue(target,root)
        assert target.get(extra.id).id==extra.id
        assert len(target.category_records('event','preserved_session_history_import'))==2
    finally:target.close()


def test_receipt_cannot_hide_missing_delivery(tmp_path):
    import hashlib
    root=tmp_path/'episode';root.mkdir()
    path=root/'session-evidence.sqlite3';EvidenceJournal(path).close()
    target=EvidenceJournal(tmp_path/'working.sqlite3')
    try:
        target.append('event',dict(category='preserved_session_history_import',source_path=str(path.resolve()),
            source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),record_ids=['absent']),
            episode='test',producer='test',version='1')
        import_queue(target,root)
        deficiencies=target.category_records('observation','score_acquisition_deficiency')
        assert 'missing records' in deficiencies[-1].data['payload']['reason']
    finally:target.close()


def test_sidecars_prevent_main_file_only_cache_hit(tmp_path):
    root=tmp_path/'episode';root.mkdir()
    path=root/'session-evidence.sqlite3';EvidenceJournal(path).close()
    target=EvidenceJournal(tmp_path/'working.sqlite3')
    try:
        import_queue(target,root)
        wal=root/'session-evidence.sqlite3-wal';wal.write_bytes(b'preserve uncheckpointed bytes')
        import_queue(target,root)
        deficiency=target.category_records('observation','score_acquisition_deficiency')[-1]
        assert 'sidecars present' in deficiency.data['payload']['reason']
        assert wal.read_bytes()==b'preserve uncheckpointed bytes'
        assert len(target.category_records('event','preserved_session_history_import'))==1
    finally:target.close()
