"""Deterministic falsification and question provenance in the trial journal."""

from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class Question:
    key: str
    origin: str
    mode: str
    statement: str
    observable: bool
    value: float = 0.5
    cost: float = 0.5


def choose(questions):
    eligible = [question for question in questions if question.observable]
    return min(eligible, key=lambda q: (q.cost - q.value, q.key), default=None)


def investigate(journal, key, question, predictions, observations, tolerance, evidence_ids):
    if question.mode not in ("theoretical", "experimental"):
        raise ValueError("unknown inquiry mode")
    if len(predictions) < 2 or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("expected competing predictions and a finite tolerance")
    if question.observable and (not observations or not evidence_ids):
        raise ValueError("independent evidence required")
    if not all(math.isfinite(x) for x in observations):
        raise ValueError("nonfinite observations")
    outcomes = {}
    if question.observable:
        for name, expected in predictions.items():
            if len(expected) != len(observations) or not all(math.isfinite(x) for x in expected):
                raise ValueError("invalid prediction")
            outcomes[name] = max(abs(a - b) for a, b in zip(expected, observations, strict=True))
    surviving = [name for name, error in outcomes.items() if error <= tolerance]
    if not question.observable:
        status = "NEEDS_EXTERNAL_EVIDENCE"
    elif len(surviving) == 1:
        status = "VERIFIED_SIM" if question.mode == "experimental" else "INFERRED"
    elif surviving:
        status = "INCONCLUSIVE"
    else:
        status = "CONTRADICTED"
    record = {"question": asdict(question), "predictions": predictions,
              "evidence_ids": evidence_ids, "tolerance": tolerance,
              "errors": outcomes, "surviving": surviving, "status": status}
    journal.append(key, "inquiry", record)
    return record
