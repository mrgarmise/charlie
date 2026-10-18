"""Bounded durable diagnostic PPAL tactical outcomes.

This is evidence collection, not a qualified live strategy or score learner.
Only confirmed same-track, completed response windows enter this artifact.
The existing controller and safety decisions never consult it for actuation.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import math
import os
import tempfile

SCHEMA = "charlie-tactical-diagnostic-evidence-v1"
MOVES = frozenset(("N", "NE", "E", "SE", "S", "SW", "W", "NW"))
MAX_ROWS = 512


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class TacticalDiagnosticMemory:
    """Persistent observation ledger; not an activated physical PPAL policy."""

    def __init__(self, path):
        self.path = Path(path).expanduser()
        self.rows = []
        if self.path.is_file():
            data = json.loads(self.path.read_text())
            if (not isinstance(data, dict) or data.get("schema") != SCHEMA
                    or not isinstance(data.get("outcomes"), list)
                    or len(data["outcomes"]) > MAX_ROWS):
                raise ValueError("invalid tactical diagnostic state; refusing to load")
            for row in data["outcomes"]:
                if not self._valid_row(row):
                    raise ValueError("invalid tactical diagnostic evidence; refusing to load")
            self.rows = data["outcomes"]

    @staticmethod
    def _valid_row(row):
        if not isinstance(row, dict):
            return False
        return (all(isinstance(row.get(k), str) and row[k] for k in
                    ("episode", "prediction_id", "evidence_id", "source_sha256"))
                and row.get("move") in MOVES
                and isinstance(row.get("fire"), str)
                and row.get("result") in ("supported", "contradicted")
                and isinstance(row.get("along"), (float, int))
                and not isinstance(row.get("along"), bool)
                and math.isfinite(row["along"])
                and len(row["source_sha256"]) == 64)

    def record(self, outcome, *, episode, evidence_id):
        """Append one authenticated-in-session outcome, never archive replay.

        The episode identifier is a local recording origin, not a certification
        of independent gameplay. Copies must not be added as new data.
        """
        if (not isinstance(outcome, dict) or outcome.get("eligible") is not True
                or outcome.get("identity_status") != "confirmed"
                or outcome.get("result") not in ("supported", "contradicted")
                or not isinstance(outcome.get("actual_action"), dict)
                or outcome["actual_action"].get("move") not in MOVES
                or not isinstance(outcome["actual_action"].get("fire"), str)
                or not isinstance(outcome.get("along"), (float, int))
                or isinstance(outcome["along"], bool)
                or not math.isfinite(outcome["along"])
                or not all(isinstance(s, str) and s for s in
                           (episode, evidence_id, outcome.get("prediction_id")))):
            return False
        row = dict(episode=episode, evidence_id=evidence_id,
                   prediction_id=outcome["prediction_id"],
                   move=outcome["actual_action"]["move"],
                   fire=outcome["actual_action"]["fire"],
                   result=outcome["result"], along=outcome["along"],
                   source_sha256=sha256(_canonical(outcome).encode()).hexdigest())
        if not self._valid_row(row):
            return False
        key = (episode, row["prediction_id"])
        for old in self.rows:
            if (old["episode"], old["prediction_id"]) == key:
                if old != row:
                    raise ValueError("conflicting tactical observation identity")
                return False
        if len(self.rows) >= MAX_ROWS:
            raise RuntimeError("tactical diagnostic ledger full; preserve existing evidence and rotate under review")
        previous = self.rows
        self.rows = previous + [row]
        try:
            self._save()
        except BaseException:
            self.rows = previous
            raise
        return True

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = _canonical(dict(schema=SCHEMA, outcomes=self.rows)) + "\n"
        fd, name = tempfile.mkstemp(prefix=".tactical-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as out:
                os.fchmod(out.fileno(), 0o600)
                out.write(payload)
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def summary(self, move, fire):
        """Read-only evidence basis for counterfactual offline PPAL valuation."""
        selected = [r for r in self.rows if r["move"] == move and r["fire"] == fire]
        episodes = sorted({r["episode"] for r in selected})
        contradicted = [r for r in selected if r["result"] == "contradicted"]
        return dict(samples=len(selected), episode_origins=len(episodes),
                    contradicted=len(contradicted),
                    supported=len(selected)-len(contradicted),
                    evidence_ids=[r["evidence_id"] for r in selected],
                    eligible_for_physical_activation=False,
                    interpretation="retained same-track diagnostics; session origins are not independent game certificates")
