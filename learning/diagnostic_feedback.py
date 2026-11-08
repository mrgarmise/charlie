"""Scoped evidence interpretation for an Executive's predictive-memory feedback.

A scientific investigation can be useful while its hypothesis is false.  This
module reports *prediction reliability* to MemoryEvaluator, not value of the
investigation method, gameplay score, or independent acceptance.  Unknown
outcomes MUST NOT become negative examples.
"""
from __future__ import annotations


def prediction_feedback(result: str, *, eligible: bool = True) -> tuple[str, str] | None:
    """Return a verdict only for an actual interpretable prediction resolution.

    'supported' and 'contradicted' assess the frozen hypothesis.  They do not
    rate how worthwhile the investigative method was.  'unresolved' means
    missing/inadequate evidence; it must not penalize the predicted hypothesis.
    """
    if not eligible or result == "unresolved":
        return None
    if result == "supported":
        return ("helpful",
                "Observed diagnostic result supports the frozen prediction only; "
                "not a causal explanation, useful method, independent trial, or score gain")
    if result == "contradicted":
        return ("harmful",
                "Observed diagnostic result contradicts the frozen prediction only; "
                "a falsifying experiment may itself be informative; no score attribution")
    raise ValueError("unsupported prediction resolution: " + str(result))
