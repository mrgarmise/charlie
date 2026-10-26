"""Explicit, append-only retrospective score-photo reading attestation.

An image-reviewer's later confirmation that they independently read the
photograph may qualify an existing immutable score annotation as a human label.
It never backdates the original review, changes the score, creates a new
independent game, or allows machine-predicted labels to become ground truth.
"""
from __future__ import annotations


CATEGORY = "score_photo_read_attestation"
SCHEMA = "score-photo-reading-attestation-v1"


def attested_photo_annotation_ids(journal):
    """Return original annotation IDs with exact, source-linked attestation."""
    approved = set()
    for row in journal.category_records("observation", CATEGORY):
        p = row.data["payload"]
        if p.get("schema") != SCHEMA or p.get("photo_read_confirmed") is not True:
            continue
        annotation_id = p.get("annotation_id")
        proposal_id = p.get("proposal_id")
        if not isinstance(annotation_id, str) or not isinstance(proposal_id, str):
            continue
        if not {annotation_id, proposal_id}.issubset(set(row.data["sources"])):
            continue
        try:
            a = journal.get(annotation_id).data["payload"]
            proposal = journal.get(proposal_id).data["payload"]
        except KeyError:
            continue
        if (a.get("category") != "score_human_annotation"
                or proposal.get("category") != "score_review_proposal"
                or a.get("proposal_id") != proposal_id
                or a.get("annotator") != p.get("annotator")
                or a.get("artifact_sha256") != proposal["artifact"]["sha256"]
                or p.get("artifact_sha256") != proposal["artifact"]["sha256"]
                or a.get("synthetic") is True
                or a.get("verdict") not in ("confirm", "correct", "unreadable")):
            continue
        approved.add(annotation_id)
    return approved
