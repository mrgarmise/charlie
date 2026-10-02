"""Dense evidentiary journal beneath Experience; never a memory selector.

Append-only SQLite transactions preserve canonical JSON, stable content IDs and
ordered commitments. External artifacts are addressed by hash, not copied here.
Replay commitments are explicitly replay commitments, never historical forecasts.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time

SCHEMA = "charlie-evidence-v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class EvidenceRecord:
    sequence: int
    id: str
    document: str
    committed_at: str

    @property
    def data(self):
        # A fresh decoded value prevents nested mutation of committed history.
        return json.loads(self.document)


class EvidenceJournal:
    """One bounded episode's lab notebook, separate from selective MARM stores."""

    def __init__(self, path, on_progress=None):
        self.path = Path(path)
        self.on_progress = on_progress
        self._batch_depth = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS records (
                sequence INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
                document TEXT NOT NULL, committed_at TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS immutable_update BEFORE UPDATE ON records
            BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_delete BEFORE DELETE ON records
            BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;
            CREATE INDEX IF NOT EXISTS evidence_kind ON records(json_extract(document,'$.kind'));
            CREATE INDEX IF NOT EXISTS evidence_resolution_prediction ON records(
                json_extract(document,'$.kind'), json_extract(document,'$.payload.prediction_id'));
            CREATE INDEX IF NOT EXISTS evidence_observation_time ON records(
                json_extract(document,'$.kind'), json_extract(document,'$.episode'), json_extract(document,'$.at'));
        """)
        self.conn.commit()
        self.verify()

    def close(self):
        self.conn.close()

    def records(self, kind=None):
        query = "SELECT sequence,id,document,committed_at FROM records"
        args = ()
        if kind is not None:
            query += " WHERE json_extract(document,'$.kind')=?"
            args = (kind,)
        return [EvidenceRecord(*r) for r in self.conn.execute(query+" ORDER BY sequence",args)]

    def get(self, identifier):
        row = self.conn.execute("SELECT sequence,id,document,committed_at FROM records WHERE id=?",
                                (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        return EvidenceRecord(*row)

    def verify(self):
        for values in self.conn.execute("SELECT sequence,id,document,committed_at FROM records ORDER BY sequence"):
            row = EvidenceRecord(*values)
            if row.data.get('schema') != SCHEMA or digest(row.data) != row.id:
                raise ValueError("invalid evidence schema or content digest")
            for source in row.data['sources']:
                if self.get(source).sequence >= row.sequence:
                    raise ValueError("evidence references must precede commitment")
            if self.on_progress: self.on_progress()

    @contextmanager
    def batch(self):
        """Atomic durable observation unit; synchronous durability is unchanged."""
        outer = self._batch_depth == 0
        if outer: self.conn.execute('BEGIN')
        self._batch_depth += 1
        try:
            yield
            if outer: self.conn.commit()
        except BaseException:
            if outer: self.conn.rollback()
            raise
        finally:
            self._batch_depth -= 1
        if outer and self.on_progress: self.on_progress()

    def existing_prediction(self, expected, *, episode, at, deadline, sources, producer,
                            version, mode='replay_prospective'):
        """Recover only an exact committed forecast; no hindsight creation."""
        doc = dict(schema=SCHEMA, kind='prediction', episode=episode, at=at,
                   producer=producer, version=version, sources=list(sources), provenance={},
                   payload=dict(expected=expected, deadline=deadline, mode=mode))
        try: return self.get(digest(doc))
        except KeyError: return None

    def resolution_for(self, prediction_id):
        row = self.conn.execute("SELECT sequence,id,document,committed_at FROM records WHERE "
            "json_extract(document,'$.kind')='resolution' AND "
            "json_extract(document,'$.payload.prediction_id')=?", (prediction_id,)).fetchone()
        return EvidenceRecord(*row) if row else None

    def append(self, kind, payload, *, episode, at=None, sources=(), producer,
               version, provenance=None):
        if kind in ('prediction','resolution'):
            raise ValueError('use predict/resolve lifecycle for reserved records')
        return self._append(kind,payload,episode=episode,at=at,sources=sources,
                            producer=producer,version=version,provenance=provenance)

    def _append(self, kind, payload, *, episode, at=None, sources=(), producer,
                version, provenance=None):
        if not kind or not episode or not producer or not version:
            raise ValueError("kind, episode, producer and version are required")
        if at is not None and (not math.isfinite(at) or at < 0):
            raise ValueError("timestamp must be finite; unknown time is None")
        for source in sources:
            if self.get(source).data['episode'] != episode:
                raise ValueError("cross-episode references need a separate consolidation layer")
        doc = dict(schema=SCHEMA, kind=kind, episode=episode, at=at,
                   producer=producer, version=version, sources=list(sources),
                   provenance=provenance or {}, payload=payload)
        identifier = digest(doc)
        try: existing = self.get(identifier)
        except KeyError: existing = None
        if existing is not None:
            if self.on_progress and not self._batch_depth: self.on_progress()
            return existing
        def insert():
            self.conn.execute("INSERT OR IGNORE INTO records(id,document,committed_at) VALUES (?,?,?)",
                              (identifier, canonical(doc), datetime.now(timezone.utc).isoformat()))
        if self._batch_depth: insert()
        else:
            with self.conn: insert()
        if self.on_progress and not self._batch_depth: self.on_progress()
        return self.get(identifier)

    def predict(self, expected, *, episode, at, deadline, sources, producer,
                version, mode="replay_prospective"):
        if mode not in ('replay_prospective', 'live_prospective'):
            raise ValueError("hindsight is not a prospective prediction")
        if mode == 'live_prospective' and abs(time.monotonic()-at) > .1:
            raise ValueError('live prediction must use current process monotonic time')
        if not math.isfinite(deadline) or deadline <= at or not sources:
            raise ValueError("prediction needs past evidence and a future horizon")
        # Reject predictions after the journal has already observed their outcome.
        latest = self.conn.execute("SELECT MAX(json_extract(document,'$.at')) FROM records WHERE json_extract(document,'$.kind')='observation' AND json_extract(document,'$.episode')=?",(episode,)).fetchone()[0]
        if latest is not None and latest > at:
            raise ValueError("hindsight: later observations already committed")
        for source in sources:
            t = self.get(source).data['at']
            if t is not None and t > at:
                raise ValueError("prediction cannot depend on future evidence")
        return self._append('prediction', dict(expected=expected, deadline=deadline, mode=mode),
                           episode=episode, at=at, sources=sources, producer=producer, version=version)

    def resolve(self, prediction_id, *, sources, result, reason, error=None):
        prediction = self.get(prediction_id)
        p = prediction.data
        if p['kind'] != 'prediction' or result not in ('supported', 'contradicted', 'unresolved'):
            raise ValueError("resolution requires a prediction and valid verdict")
        if self.conn.execute("SELECT 1 FROM records WHERE json_extract(document,'$.kind')='resolution' AND json_extract(document,'$.payload.prediction_id')=? LIMIT 1",(prediction_id,)).fetchone():
            raise ValueError("already resolved; create a new versioned derivation")
        if not reason or (result != 'unresolved' and not sources):
            raise ValueError("resolution needs reason and outcome evidence")
        later = []
        for identifier in sources:
            row = self.get(identifier)
            t = row.data['at']
            if row.sequence <= prediction.sequence or t is None or t <= p['at']:
                raise ValueError("resolving evidence must follow prediction commitment and time")
            if result != 'unresolved' and t > p['payload']['deadline']:
                raise ValueError("outcome beyond prediction horizon")
            later.append(t)
        if error is not None and (not math.isfinite(error) or error < 0):
            raise ValueError("error must be finite and nonnegative")
        return self._append('resolution', dict(prediction_id=prediction_id, result=result,
                           reason=reason, error=error), episode=p['episode'],
                           at=max(later) if later else None, sources=(prediction_id, *sources),
                           producer=p['producer'], version=p['version'])


def read_artifact(root, reference):
    """Verify exact original bytes before returning a referenced JSON value."""
    root = Path(root).resolve()
    path = (root / reference['path']).resolve()
    if not path.is_relative_to(root):
        raise ValueError("artifact escapes episode directory")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference['sha256']:
        raise ValueError("source artifact changed; preserve original or append explicit correction")
    if reference.get('line') is not None:
        value = json.loads(raw.splitlines()[reference['line'] - 1])
    else:
        value = json.loads(raw)
    for part in reference.get('pointer', []):
        value = value[part]
    return value


class ArtifactReader:
    """Phase-local verified file snapshot; hash each immutable artifact once.

    Never cached across episodes/processes. Stat changes are rejected; returned
    values are newly decoded so an interpretation cannot alter canonical bytes.
    """
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.files = {}

    def __call__(self, reference):
        path = (self.root/reference['path']).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('artifact escapes episode directory')
        stat = path.stat()
        stamp = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if path not in self.files:
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != reference['sha256']:
                raise ValueError('source artifact changed')
            self.files[path] = (stamp, reference['sha256'], raw, raw.splitlines())
        saved, digest_value, raw, lines = self.files[path]
        if stamp != saved or reference['sha256'] != digest_value:
            raise ValueError('source artifact changed during evidence processing')
        value = json.loads(lines[reference['line']-1] if reference.get('line') is not None else raw)
        for part in reference.get('pointer', []):
            value = value[part]
        return value
