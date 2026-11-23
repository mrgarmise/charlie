"""Bounded SQLite research notebook. All mutating operations commit atomically."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
import tempfile
import unicodedata

UTC = timezone.utc
APP_ID = 0x43444A31
SCHEMA = 2
MAX_QUESTIONS = 1024
MAX_EVENTS = 65536
LEASE_SECONDS = 3600
STATUSES = frozenset(("verified_formal", "supported_empirical", "hypothesis", "contradicted",
                      "unknown", "blocked", "requires_observation"))
STAGES = ("PREFLIGHT", "SELECT", "RETRIEVE", "FRAME", "DECOMPOSE", "DERIVE",
          "CHALLENGE", "VERIFY", "ASSESS", "JOURNAL", "NEXT")
_IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,159}\Z")


def timestamp(value=None):
    if value is None:
        return time.time()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("timezone required")
        value = value.timestamp()
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("finite timestamp required")
    datetime.fromtimestamp(value, UTC)
    return float(value)


def iso(value):
    return datetime.fromtimestamp(value, UTC).isoformat()


def identifier(value):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("invalid record identifier")
    return value


def plain(value, limit=640):
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > limit:
        raise ValueError("bounded nonempty text required")
    if any(unicodedata.category(c) in ("Cc", "Cf") and c not in "\r\n\t" for c in value):
        raise ValueError("unexpected control character")
    return " ".join(value.split())


def fingerprint(text):
    return hashlib.sha256(unicodedata.normalize("NFKC", text).casefold().strip(" ?.!").encode()).hexdigest()


def packed(value, limit=16384):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if len(data.encode()) > limit:
        raise ValueError("record exceeds journal budget")
    return data


def private_file(path):
    path = Path(path)
    if path.is_symlink():
        raise PermissionError("journal must be a private regular file")
    stat = path.stat()
    if not path.is_file() or stat.st_uid != os.geteuid() or stat.st_mode & 0o077 or stat.st_nlink != 1:
        raise PermissionError("private journal owned by current user required")


class Journal:
    def __init__(self, path, *, read_only=False):
        self.path = Path(path).absolute()
        if not self.path.exists() and not read_only:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(fd)
        private_file(self.path)
        self.read_only = read_only
        mode = "ro" if read_only else "rw"
        self.db = sqlite3.connect(self.path.as_uri() + "?mode=" + mode, uri=True, timeout=0.25,
                                  isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("PRAGMA trusted_schema=OFF")
            if read_only:
                self.db.execute("PRAGMA query_only=ON")
                if self._pragma("application_id") != APP_ID or self._pragma("user_version") != SCHEMA:
                    raise ValueError("journal schema requires operator migration")
            else:
                self._migrate()
                self.db.execute("PRAGMA journal_mode=WAL")
                self.db.execute("PRAGMA synchronous=FULL")
                self.db.execute("PRAGMA wal_autocheckpoint=128")
                self.db.execute("PRAGMA journal_size_limit=1048576")
                self.db.execute(f"PRAGMA max_page_count={64 * 1024**2 // self._pragma('page_size')}")
        except BaseException:
            self.close()
            raise

    def _pragma(self, key):
        return self.db.execute("PRAGMA " + key).fetchone()[0]

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @contextmanager
    def _write(self):
        if self.read_only:
            raise PermissionError("journal opened read-only")
        wal = Path(str(self.path) + "-wal")
        if wal.exists() and wal.stat().st_size > 4 * 1024**2:
            if self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]:
                raise OSError("journal checkpoint blocked; writer paused")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def _migrate(self):
        with self._write():
            version = self._pragma("user_version")
            if version == 0:
                if self._pragma("application_id") or self.db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone():
                    raise ValueError("refusing to initialize a different database")
                for sql in (
                    "CREATE TABLE questions(id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL, body TEXT NOT NULL, origin TEXT NOT NULL, depth INTEGER NOT NULL, added REAL NOT NULL)",
                    "CREATE TABLE edges(child TEXT REFERENCES questions, parent TEXT, kind TEXT, PRIMARY KEY(child,parent,kind))",
                    "CREATE TABLE sessions(id TEXT PRIMARY KEY, question_id TEXT REFERENCES questions, started REAL NOT NULL, updated REAL NOT NULL, state TEXT NOT NULL, stage TEXT NOT NULL, checkpoint TEXT NOT NULL, record TEXT, retry_after REAL, metadata TEXT NOT NULL)",
                    "CREATE INDEX session_question ON sessions(question_id,updated)",
                    "CREATE TABLE events(seq INTEGER PRIMARY KEY, at REAL NOT NULL, kind TEXT NOT NULL, subject TEXT NOT NULL, data TEXT NOT NULL)",
                    "CREATE TRIGGER events_immutable_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append only'); END",
                    "CREATE TRIGGER events_immutable_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append only'); END",
                ):
                    self.db.execute(sql)
                self.db.execute(f"PRAGMA application_id={APP_ID}")
                self.db.execute("PRAGMA user_version=1")
                version = 1
            if self._pragma("application_id") != APP_ID or version not in (1, 2):
                raise ValueError("unsupported journal identity or schema version")
            if version == 1:
                self.db.execute("CREATE INDEX session_window ON sessions(state,updated)")
                self.db.execute("CREATE TABLE owner_preferences(id TEXT PRIMARY KEY REFERENCES questions, requested REAL NOT NULL)")
                self.db.execute("PRAGMA user_version=2")

    def _event(self, kind, subject, data, now):
        if self.db.execute("SELECT coalesce(max(seq),0) FROM events").fetchone()[0] >= MAX_EVENTS:
            raise OverflowError("journal event budget exhausted")
        self.db.execute("INSERT INTO events(at,kind,subject,data) VALUES(?,?,?,?)",
                        (now, kind, subject, packed(data),))

    def _add(self, source, origin, depth, now):
        question = plain(source["question"])
        digest = fingerprint(question)
        qid = identifier(source.get("id", "Q-" + digest[:24]))
        existing = self.db.execute("SELECT id,fingerprint,body FROM questions WHERE id=?", (qid,)).fetchone()
        body = dict(source, question=question, id=qid, track=plain(source.get("track", "cross_domain"), 80))
        body_text = packed(body, 4096)
        if existing:
            if existing["fingerprint"] != digest or (origin == "curriculum" and existing["body"] != body_text):
                raise ValueError("question identity or source metadata changed")
            return qid
        existing = self.db.execute("SELECT id FROM questions WHERE fingerprint=?", (digest,)).fetchone()
        if existing:
            if origin == "curriculum":
                raise ValueError("overlapping curriculum IDs require explicit reconciliation")
            return existing[0]
        if self.db.execute("SELECT count(*) FROM questions").fetchone()[0] >= MAX_QUESTIONS:
            raise OverflowError("question budget exhausted")
        self.db.execute("INSERT INTO questions VALUES(?,?,?,?,?,?)", (qid,digest,body_text,origin,depth,now))
        self._event("question-added", qid, dict(body=body,origin=origin,depth=depth), now)
        deps = body.get("prerequisites")
        if deps is None:
            deps = re.findall(r"[A-Z]+\d*-\d+", body.get("prerequisite_hint", ""))
        if not isinstance(deps, list) or len(deps) > 16:
            raise ValueError("bounded prerequisite list required")
        for dep in deps:
            if identifier(dep) == qid:
                raise ValueError("self prerequisite")
            self.db.execute("INSERT OR IGNORE INTO edges VALUES(?,?,'prerequisite')", (qid,dep))
        return qid

    def add_questions(self, rows, now=None):
        now = timestamp(now)
        with self._write():
            for n, row in enumerate(rows):
                if n >= MAX_QUESTIONS:
                    raise OverflowError("input question budget exhausted")
                self._add(row, "curriculum", 0, now)

    def queue(self, text, *, owner=False, now=None):
        if owner is not True:
            raise PermissionError("authenticated owner required")
        now = timestamp(now)
        with self._write():
            qid = self._add(dict(question=text), "owner", 0, now)
            if self.db.execute("SELECT 1 FROM owner_preferences WHERE id=?", (qid,)).fetchone() is None:
                self.db.execute("INSERT INTO owner_preferences VALUES(?,?)", (qid,now))
                self._event("owner-queued", qid, {}, now)
        return qid

    def _choices(self, now):
        rows = self.db.execute("""
            SELECT q.*,p.requested,
                (SELECT count(*) FROM edges WHERE parent=q.id AND kind='prerequisite') AS unlocks,
                (SELECT count(*) FROM sessions WHERE question_id=q.id) AS attempts,
                s.id AS last_id,s.state,s.updated,s.retry_after,s.record
            FROM questions q LEFT JOIN owner_preferences p ON p.id=q.id
            LEFT JOIN sessions s ON s.id=(SELECT id FROM sessions WHERE question_id=q.id ORDER BY updated DESC,rowid DESC LIMIT 1)
            WHERE NOT EXISTS (
                SELECT 1 FROM edges e WHERE e.child=q.id AND e.kind='prerequisite' AND NOT EXISTS (
                    SELECT 1 FROM sessions proved WHERE proved.question_id=e.parent AND proved.state='completed'
                        AND json_extract(proved.record,'$.status') IN ('verified_formal','supported_empirical')))
        """).fetchall()
        counts = {r[0]:r[1] for r in self.db.execute("""
            SELECT json_extract(q.body,'$.track'), count(*) FROM sessions s JOIN questions q
            ON q.id=s.question_id WHERE s.state='completed' GROUP BY 1
        """)}
        for row in rows:
            state = row["state"]
            if state == "in_progress" and now < row["updated"] + LEASE_SECONDS:
                continue
            if state == "deferred" and now < row["retry_after"]:
                continue
            if state == "completed" and row["requested"] is None:
                continue
            body = json.loads(row["body"])
            factors = dict(owner=1000 if row["requested"] is not None else 0,
                           start=5 if body.get("priority") == "start" else 0,
                           prerequisite_unlocks=min(row["unlocks"], 4),
                           evidence=2 if body.get("evidence_requirement") else 0,
                           novelty=3 if not row["attempts"] else 0,
                           track_diversity=-min(counts.get(body["track"], 0), 20),
                           prior_attempts=-min(row["attempts"], 10))
            score = sum(factors.values())
            body.update(score=score, score_factors=factors, selection_reason=", ".join(
                f"{k} {v:+d}" for k,v in factors.items() if v) or "eligible question",
                previous_session_id=row["last_id"], origin=row["origin"])
            yield body

    def select(self, now=None):
        return min(self._choices(timestamp(now)), key=lambda q:(-q["score"], q["id"]), default=None)

    def session(self, session_id):
        row = self.db.execute("SELECT * FROM sessions WHERE id=?", (identifier(session_id),)).fetchone()
        if not row:
            return None
        result = dict(row)
        for key in ("record","checkpoint","metadata"):
            result[key] = json.loads(row[key]) if row[key] is not None else None
        return result

    def begin(self, session_id, question_id, now=None, **metadata):
        sid, qid, now = identifier(session_id), identifier(question_id), timestamp(now)
        with self._write():
            if self.session(sid) is not None:
                raise ValueError("commission already recorded")
            choice = next((q for q in self._choices(now) if q["id"] == qid), None)
            if choice is None:
                raise ValueError("question unavailable")
            last_id = choice["previous_session_id"]
            if last_id and self.session(last_id)["state"] == "in_progress":
                self._defer(last_id, "expired interrupted checkpoint", now, 0)
            meta = dict(metadata)
            meta.update(selection_reason=choice["selection_reason"], score_factors=choice["score_factors"])
            self.db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?,?)",
                (sid,qid,now,now,"in_progress","PREFLIGHT","{}",None,None,packed(meta,4096)))
            self._event("session-start",sid,dict(question_id=qid,metadata=meta),now)
        return self.session(sid)

    def _active(self, sid, now):
        row = self.session(sid)
        if not row or row["state"] != "in_progress" or now < row["updated"]:
            raise ValueError("session is closed, missing, or timestamp regressed")
        return row

    def checkpoint(self, session_id, stage, data, now=None):
        now = timestamp(now)
        if stage not in STAGES or not isinstance(data, dict):
            raise ValueError("unknown stage or invalid checkpoint")
        with self._write():
            row = self._active(session_id,now)
            if STAGES.index(stage) < STAGES.index(row["stage"]):
                raise ValueError("checkpoint stage regressed")
            self._event("checkpoint",session_id,dict(stage=stage,data=data),now)
            self.db.execute("UPDATE sessions SET stage=?,checkpoint=?,updated=? WHERE id=?",
                            (stage,packed(data),now,session_id))

    def _defer(self, sid, reason, now, cooldown):
        self._active(sid,now)
        self._event("deferred",sid,dict(reason=reason,retry_after=now+cooldown),now)
        self.db.execute("UPDATE sessions SET state='deferred',record=?,updated=?,retry_after=? WHERE id=?",
                        (packed(dict(reason=reason)),now,now+cooldown,sid))

    def defer(self, session_id, reason, now=None, cooldown=3600):
        if type(cooldown) is not int or not 60 <= cooldown <= 86400:
            raise ValueError("cooldown must be 60–86400 seconds")
        with self._write():
            self._defer(session_id,plain(reason),timestamp(now),cooldown)

    def finish(self, session_id, record, now=None):
        now = timestamp(now)
        if not isinstance(record, dict) or record.get("status") not in STATUSES:
            raise ValueError("evidence status required")
        record = dict(record)
        packed(record)
        for key in ("findings","citations","checks","uncertainty","followups"):
            value = record.setdefault(key, [])
            if not isinstance(value, list) or len(value) > 16:
                raise ValueError("bounded list required for " + key)
        for item in record["findings"] + record["uncertainty"]:
            plain(item, 1600)
        for citation in record["citations"]:
            identifier(citation["id"] if isinstance(citation,dict) else citation)
        if record["status"] == "supported_empirical" and not record["citations"]:
            raise ValueError("empirical support requires sources")
        if not all(isinstance(check, dict) for check in record["checks"]):
            raise ValueError("structured checks required")
        if record["status"] == "verified_formal" and not any(
                check.get("valid") is True and check.get("tool") in ("rational_arithmetic", "unit_check")
                for check in record["checks"]):
            raise ValueError("formal verification requires check evidence")
        if len(record["followups"]) > 3:
            raise ValueError("follow-up budget exceeded")
        with self._write():
            row = self._active(session_id,now)
            qid = row["question_id"]
            parent = self.db.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
            record["followup_ids"] = []
            if parent["depth"] < 2:
                for follow in record["followups"]:
                    body = dict(follow) if isinstance(follow,dict) else dict(question=follow)
                    body.setdefault("track",json.loads(parent["body"])["track"])
                    child = self._add(body,"followup",parent["depth"]+1,now)
                    if child == qid or child in record["followup_ids"]:
                        continue
                    # Reusing an older question is a connection, never a new dependency.
                    self.db.execute("INSERT OR IGNORE INTO edges VALUES(?,?,'followup')",(child,qid))
                    record["followup_ids"].append(child)
            self._event("session-committed",session_id,record,now)
            self.db.execute("UPDATE sessions SET state='completed',stage='NEXT',record=?,updated=? WHERE id=?",
                            (packed(record),now,session_id))
            self.db.execute("DELETE FROM owner_preferences WHERE id=?",(qid,))
        return record

    def correct(self, session_id, note, *, owner=False, now=None):
        if owner is not True:
            raise PermissionError("authenticated owner required")
        with self._write():
            row = self.session(session_id)
            if not row or row["state"] != "completed":
                raise ValueError("committed session required")
            self._event("owner-correction",session_id,dict(note=plain(note,1600)),timestamp(now))

    def snapshot(self, destination):
        """Consistent SQLite backup; publish exclusively after integrity validation."""
        target = Path(destination).absolute()
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent)
        os.close(fd)
        try:
            copy = sqlite3.connect(tmp)
            try:
                self.db.backup(copy)
                if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("backup integrity check failed")
                if copy.execute("PRAGMA foreign_key_check").fetchone():
                    raise ValueError("backup has dangling references")
                copy.execute("PRAGMA journal_mode=DELETE")
            finally:
                copy.close()
            with open(tmp,"rb") as stream:
                os.fsync(stream.fileno())
            os.link(tmp,target)
            handle = os.open(target.parent, os.O_DIRECTORY)
            try:
                os.fsync(handle)
            finally:
                os.close(handle)
        finally:
            os.unlink(tmp)

    def digest(self, now=None, *, topic=None, question_id=None, session_id=None, all_time=False):
        end = timestamp(now)
        today = datetime.fromtimestamp(end,UTC).replace(hour=0,minute=0,second=0,microsecond=0)
        start = (today - timedelta(days=6)).timestamp()
        clauses = ["s.updated<=?"]
        args = [end]
        if not all_time:
            clauses.append("s.updated>=?")
            args.append(start)
        if topic:
            clauses.append("(instr(lower(q.body),lower(?))>0 OR instr(lower(coalesce(s.record,'')),lower(?))>0)")
            args.extend((topic,topic))
        for column, val in (("q.id",question_id),("s.id",session_id)):
            if val:
                clauses.append(column + "=?")
                args.append(identifier(val))
        sql = " FROM sessions s JOIN questions q ON q.id=s.question_id WHERE " + " AND ".join(clauses)
        rows = self.db.execute("SELECT s.*,q.body"+sql+" ORDER BY s.updated DESC,s.rowid DESC LIMIT 101",args).fetchall()
        data = dict(schema="ResearchDigest/v1",time_window=dict(start=None if all_time else iso(start),
                    end=iso(end),timezone="UTC"),completed_sessions=[],attempted_question_ids=[],
                    in_progress_question_ids=[],deferred_question_ids=[],blockers=[],followups=[],
                    truncated=len(rows)>100, fallback=False)
        for row in rows[:100]:
            q = json.loads(row["body"])
            if q["id"] not in data["attempted_question_ids"]:
                data["attempted_question_ids"].append(q["id"])
            record = json.loads(row["record"] or "{}")
            if row["state"] != "completed":
                data[row["state"]+"_question_ids"].append(q["id"])
                if row["state"] == "deferred":
                    data["blockers"].append(dict(id=q["id"],reason=record["reason"]))
                continue
            corrections = [dict(at=iso(c[0]),note=json.loads(c[1])["note"]) for c in self.db.execute(
                "SELECT at,data FROM events WHERE subject=? AND kind='owner-correction' AND at<=? ORDER BY seq DESC LIMIT 8",
                (row["id"],end))]
            citations = [c["id"] if isinstance(c,dict) else c for c in record["citations"]]
            summary = dict(id=row["id"],question_id=q["id"],question=q["question"],track=q["track"],
                date=iso(row["updated"]),status=record["status"],findings=record["findings"],
                uncertainty=record["uncertainty"],citations=citations,checks=record["checks"],
                followup_ids=record["followup_ids"],corrections=corrections,
                selection_reason=json.loads(row["metadata"])["selection_reason"])
            data["completed_sessions"].append(summary)
            data["followups"].extend(summary["followup_ids"])
            if record["status"] in ("unknown","blocked","requires_observation","contradicted"):
                data["blockers"].append(dict(id=q["id"],reason=" ".join(record["uncertainty"]) or record["status"]))
        return data
