"""Face-search observations and conservative advice from past outcomes."""

import json
from uuid import uuid4

from .former import Experience
from .marm import MarmWriteError


def preferred_direction(gateway, decision_id=None):
    """Use a preference only after independent evidence favors one side."""
    try:
        memories = gateway.recall("face search reacquired direction", limit=20)
    except MarmWriteError:
        return None
    outcomes = {}
    for memory in memories:
        marker = "Metadata: "
        if marker not in memory.content:
            continue
        try:
            record = json.loads(memory.content.split(marker, 1)[1].splitlines()[0])
        except (ValueError, IndexError):
            continue
        if (not isinstance(record, dict)
                or record.get("source") != "head:face-search"
                or not isinstance(record.get("tags"), list)
                or "head-search" not in record["tags"]
                or record.get("kind") != "outcome"
                or not isinstance(record.get("confidence"), (int, float))
                or record["confidence"] < 0.7):
            continue
        evidence = record.get("evidence")
        subject = record.get("subject")
        if not evidence or subject not in ("LEFT", "RIGHT"):
            continue
        # A repeated semantic hit or duplicate remote log is one observation.
        outcomes[evidence] = (subject, memory.evaluation_id)
    counts = {side: sum(value[0] == side for value in outcomes.values()) for side in ("LEFT", "RIGHT")}
    side = max(counts, key=counts.get)
    if counts[side] < 3 or counts[side] - counts["RIGHT" if side == "LEFT" else "LEFT"] < 2:
        return None
    used = [identifier for value, identifier in outcomes.values()
            if value == side and identifier]
    if decision_id and used and hasattr(gateway, "record_decision"):
        gateway.record_decision(decision_id, "head:face-search", used)
    return side


class HeadSearchMemory:
    def __init__(self, gateway):
        self.gateway = gateway
        self.run_id = uuid4().hex
        self.attempt = 0
        self.searching = False
        self.direction = None

    def observe(self, behavior, face, status):
        """Call after update_face; snapshot search direction before that call."""
        state = status.get("state", "")
        if face is None and state in ("LOCAL_SEARCH", "SENTRY_LOCAL_SEARCH", "SENTRY_TURN"):
            if not self.searching:
                self.attempt += 1
                self.searching = True
            if behavior.sentry_preferred_direction:
                self.direction = behavior.sentry_preferred_direction
            elif self.direction is None and behavior.search_direction:
                self.direction = "LEFT" if behavior.search_direction > 0 else "RIGHT"
            return
        if face is not None and self.searching:
            side = self.direction
            if side in ("LEFT", "RIGHT"):
                self.gateway.remember(Experience(
                    kind="outcome", summary=f"Face detected after search starting {side}",
                    source="head:face-search", goal="reacquire a face",
                    outcome="face detected (identity unverified)", subject=side,
                    confidence=min(0.95, max(0.7, float(face.get("score", 0.7)))),
                    significant=True, tags=("head-search", "face-detected"),
                    evidence=f"head:{self.run_id}:{self.attempt}",
                ))
            self.searching = False
            self.direction = None
        elif face is None and state == "SENTRY_DONE":
            self.searching = False
            self.direction = None
