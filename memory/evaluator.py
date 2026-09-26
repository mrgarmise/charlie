"""Revisable memory selection and usefulness evidence.

Episodes are observations. Usefulness feedback needs an explicit comparison or
human correction; temporal proximity alone never counts as proof of benefit.
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Literal

from .former import CandidateMemory, Experience, MemoryFormer
from .marm import DEFAULT_OUTBOX

DEFAULT_EVALUATIONS = DEFAULT_OUTBOX.with_name("memory-evaluation.sqlite3")


@dataclass(frozen=True)
class Evaluation:
    id: str
    candidate: CandidateMemory
    priority: float
    promote: bool
    reason: str


class MemoryEvaluator:
    """Keeps provisional evidence, category statistics, decisions and corrections."""

    THRESHOLD = 0.4

    def __init__(self, path=DEFAULT_EVALUATIONS, exploration_rate=0.05):
        if not 0 <= exploration_rate <= 1:
            raise ValueError("exploration_rate must be within [0, 1]")
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.exploration_rate = exploration_rate
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY, feature TEXT NOT NULL, payload TEXT NOT NULL,
                    status TEXT NOT NULL, priority REAL NOT NULL, reason TEXT NOT NULL,
                    remote_key TEXT
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY, memory_id TEXT NOT NULL, verdict TEXT NOT NULL,
                    weight REAL NOT NULL, rationale TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT NOT NULL, memory_id TEXT NOT NULL, task TEXT NOT NULL,
                    PRIMARY KEY(decision_id, memory_id)
                );
                CREATE TABLE IF NOT EXISTS corrections (
                    memory_id TEXT PRIMARY KEY, replacement TEXT NOT NULL, rationale TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_candidates_remote ON candidates(remote_key);
            """)

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    @staticmethod
    def feature(event: Experience) -> str:
        # Exact tags preserve task distinctions; broad categories share examples.
        return json.dumps([event.source, event.kind, sorted(event.tags)], separators=(",", ":"))

    @staticmethod
    def identity(candidate: CandidateMemory) -> str:
        # An evidence ID represents one episode even if its description changes.
        # Without one, identical claims are one candidate across restarts.
        key = [candidate.source, candidate.kind,
               candidate.evidence if candidate.evidence else candidate.text]
        return hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()

    def _posterior(self, conn, feature):
        row = conn.execute("""SELECT
            COALESCE(SUM(CASE WHEN verdict='helpful' THEN weight ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN verdict='harmful' THEN weight ELSE 0 END),0),
            COUNT(*) FROM evidence JOIN candidates ON candidates.id=evidence.memory_id
            WHERE candidates.feature=? AND verdict IN ('helpful','harmful')""", (feature,)).fetchone()
        good, bad, count = row
        return (1 + good) / (2 + good + bad), count

    def _score(self, conn, candidate, feature, identifier):
        usefulness, samples = self._posterior(conn, feature)
        score = candidate.importance * (0.65 + 0.7 * (usefulness - 0.5))
        if samples >= 3:
            score = max(score, usefulness * 0.75)
        explore = int(identifier[:8], 16) / 0xFFFFFFFF < self.exploration_rate
        return min(1.0, max(0.0, score)), explore

    def consider(self, event: Experience) -> Evaluation | None:
        candidate = MemoryFormer(threshold=0).consider(event)
        if candidate is None:
            return None
        identifier = self.identity(candidate)
        feature = self.feature(event)
        with self._connect() as conn:
            existing = conn.execute("SELECT status, priority, reason, payload FROM candidates WHERE id=?",
                                    (identifier,)).fetchone()
            if existing:
                return Evaluation(identifier, CandidateMemory(**json.loads(existing[3])),
                                  existing[1], existing[0] == "provisional" and existing[1] >= self.THRESHOLD,
                                  existing[2])
            score, explore = self._score(conn, candidate, feature, identifier)
            promote = score >= self.THRESHOLD or explore
            reason = "usefulness and significance" if score >= self.THRESHOLD else (
                "exploration sample" if explore else "provisional")
            conn.execute("INSERT INTO candidates(id,feature,payload,status,priority,reason) VALUES (?,?,?,?,?,?)",
                         (identifier, feature, json.dumps(candidate.to_dict()),
                          "provisional", score, reason))
        return Evaluation(identifier, candidate, score, promote, reason)

    def link_remote(self, identifier, remote_key):
        with self._connect() as conn:
            conn.execute("UPDATE candidates SET remote_key=? WHERE id=?", (remote_key, identifier))

    def resolve_remote(self, remote_key):
        with self._connect() as conn:
            row = conn.execute("SELECT id, status FROM candidates WHERE remote_key=?", (remote_key,)).fetchone()
        return row  # None means older/unmanaged MARM memory.

    def mark_promoted(self, identifier):
        with self._connect() as conn:
            conn.execute("UPDATE candidates SET status='promoted' WHERE id=? AND status='provisional'", (identifier,))

    def feedback(self, identifier: str, verdict: Literal["helpful", "harmful"],
                 evidence_id: str, rationale: str, weight: float = 1.0) -> bool:
        """Explicit, deduplicated assessment; never infer from action timing."""
        if verdict not in ("helpful", "harmful") or not evidence_id.strip() or not rationale.strip():
            raise ValueError("Feedback needs a verdict, unique evidence ID and rationale")
        if not 0 < weight <= 2:
            raise ValueError("Feedback weight must be within (0, 2]")
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM candidates WHERE id=?", (identifier,)).fetchone() is None:
                raise KeyError(identifier)
            result = conn.execute("INSERT OR IGNORE INTO evidence VALUES (?,?,?,?,?)",
                                  (evidence_id, identifier, verdict, weight, rationale))
            inserted = result.rowcount == 1
        if inserted:
            self.refresh()
        return inserted

    def refresh(self):
        """Re-rate active claims as contrary evidence arrives or is revised."""
        with self._connect() as conn:
            rows = conn.execute("SELECT id, feature, payload, status FROM candidates WHERE status!='superseded'").fetchall()
            for identifier, feature, payload, status in rows:
                candidate = CandidateMemory(**json.loads(payload))
                priority, _ = self._score(conn, candidate, feature, identifier)
                if status in ('promoted', 'dormant'):
                    new_status = 'promoted' if priority >= self.THRESHOLD else 'dormant'
                else:
                    new_status = 'provisional'
                conn.execute("UPDATE candidates SET priority=?, status=? WHERE id=?",
                             (priority, new_status, identifier))

    def record_decision(self, decision_id: str, task: str, memory_ids: list[str]):
        """Track actual use, not merely recall. No usefulness credit yet."""
        if not decision_id.strip() or not task.strip():
            raise ValueError("Decision and task IDs are required")
        with self._connect() as conn:
            for identifier in set(memory_ids):
                if conn.execute("SELECT 1 FROM candidates WHERE id=? AND status='promoted'", (identifier,)).fetchone() is None:
                    raise KeyError(identifier)
                conn.execute("INSERT OR IGNORE INTO decisions VALUES (?,?,?)",
                             (decision_id, identifier, task))

    def assess_decision(self, decision_id: str, verdict: Literal["helpful", "harmful"],
                        evidence_id: str, comparison: str, weight: float = 1.0) -> int:
        """Credit an outcome only when a comparison/rationale is supplied."""
        if not comparison.strip():
            raise ValueError("Explain the comparison behind this assessment")
        with self._connect() as conn:
            ids = [row[0] for row in conn.execute("SELECT memory_id FROM decisions WHERE decision_id=?",
                                                   (decision_id,))]
        if not ids:
            raise KeyError(decision_id)
        # Split credit among influences; never count one outcome N times.
        return sum(self.feedback(identifier, verdict, evidence_id + ":" + identifier,
                                 comparison, weight / len(ids)) for identifier in ids)

    def correct(self, identifier: str, replacement: str, rationale: str):
        """Supersede a false or stale memory without erasing its history."""
        if not replacement.strip() or not rationale.strip():
            raise ValueError("Correction and rationale are required")
        with self._connect() as conn:
            row = conn.execute("SELECT feature FROM candidates WHERE id=?", (identifier,)).fetchone()
            if row is None:
                raise KeyError(identifier)
            conn.execute("INSERT INTO corrections VALUES (?,?,?) ON CONFLICT(memory_id) DO UPDATE SET replacement=excluded.replacement, rationale=excluded.rationale",
                         (identifier, replacement, rationale))
            conn.execute("UPDATE candidates SET status='superseded' WHERE id=?", (identifier,))
        # Correction is scoped to this claim; it does not condemn every memory
        # from the same producer/category. Other claims need their own evidence.

    def is_active(self, identifier: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT status FROM candidates WHERE id=?", (identifier,)).fetchone()
        return row is None or row[0] == "promoted"

    def review_pending(self, limit=100) -> list[Evaluation]:
        """Reconsider provisional candidates after feedback changes a category."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be within 1..1000")
        selections = []
        with self._connect() as conn:
            rows = conn.execute("SELECT id, feature, payload FROM candidates WHERE status='provisional' ORDER BY rowid LIMIT ?", (limit,)).fetchall()
            for identifier, feature, payload in rows:
                candidate = CandidateMemory(**json.loads(payload))
                score, _ = self._score(conn, candidate, feature, identifier)
                if score >= self.THRESHOLD:
                    conn.execute("UPDATE candidates SET priority=?, reason=? WHERE id=?",
                                 (score, "reconsidered with new evidence", identifier))
                    selections.append(Evaluation(identifier, candidate, score, True,
                                                 "reconsidered with new evidence"))
        return selections

    def recent(self, limit=20):
        if not 1 <= limit <= 100:
            raise ValueError("limit must be within 1..100")
        with self._connect() as conn:
            rows = conn.execute("SELECT id,status,priority,payload FROM candidates ORDER BY rowid DESC LIMIT ?",
                                (limit,)).fetchall()
        return [{"id": identifier, "status": status, "priority": priority,
                 "text": json.loads(payload)["text"]} for identifier, status, priority, payload in rows]

    def stats(self, source: str, kind: str, tags=()):
        feature = json.dumps([source, kind, sorted(tags)], separators=(",", ":"))
        with self._connect() as conn:
            posterior, count = self._posterior(conn, feature)
        return {"estimated_usefulness": posterior, "evidence_count": count}
