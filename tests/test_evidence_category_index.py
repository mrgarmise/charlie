"""Category lookup preserves append-only records and never migrates a reader."""
import hashlib
import sqlite3
from memory.evidence import EvidenceJournal


def test_category_query_uses_index_and_keeps_ordered_evidence(tmp_path):
    p=tmp_path/'journal.sqlite3';j=EvidenceJournal(p)
    try:
        first=j.append('observation',dict(category='wanted',n=1),episode='a',producer='test',version='1')
        j.append('observation',dict(category='irrelevant',blob='x'*100000),episode='a',producer='test',version='1')
        second=j.append('observation',dict(category='wanted',n=2),episode='a',producer='test',version='1')
        assert [r.id for r in j.category_records('observation','wanted')]==[first.id,second.id]
        plan=j.conn.execute("EXPLAIN QUERY PLAN SELECT sequence,id,document,committed_at FROM records "
            "WHERE json_extract(document,'$.kind')=? AND json_extract(document,'$.payload.category')=? ORDER BY sequence",
            ('observation','wanted')).fetchall()
        assert any('evidence_kind_category' in str(row) for row in plan)
        j.verify()
    finally:j.close()
    # Simulate a legacy source without the index. A read-only inspection must
    # keep its exact bytes, rather than silently upgrading an original diary.
    c=sqlite3.connect(p);c.execute('DROP INDEX evidence_kind_category');c.commit();c.close()
    before=hashlib.sha256(p.read_bytes()).hexdigest()
    reader=EvidenceJournal(p,read_only=True)
    try:assert [r.id for r in reader.category_records('observation','wanted')]==[first.id,second.id]
    finally:reader.close()
    assert hashlib.sha256(p.read_bytes()).hexdigest()==before
