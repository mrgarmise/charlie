"""Preserve and qualify earlier score reviews using explicit later user attestation.

The original score numbers, timestamps, source photo hashes and annotation
records remain untouched. The operator must explicitly opt in to adding a
*dated* attestation to the isolated pilot working journal. Dry-run by default.

This only confirms that a human read the pictured score. It never establishes
complete-game boundaries, multiple independent observers, causal learning,
final-test independence, or acceptable Hailo inference.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from memory.evidence import EvidenceJournal
from ..score_observer import ScoreObserver
from ..score_review_attestation import (
    CATEGORY, SCHEMA, attested_photo_annotation_ids,
)
from .sample import digest as selection_digest, file_sha, SCHEMA as SAMPLE_SCHEMA


def preview(journal, manifest, *, reviewer=None):
    """Enumerate only original photo-bound reviews from this frozen batch."""
    record = json.loads(Path(manifest).read_text())
    if (record.get("schema") != SAMPLE_SCHEMA
            or selection_digest({k: v for k, v in record.items() if k != "digest"})
               != record.get("digest")):
        raise ValueError("frozen sampler selection has changed")
    selection_sha = file_sha(manifest)
    original_images = {
        row["source_image_sha256"]: row
        for row in record["selected"]
    }
    if len(original_images) != len(record["selected"]):
        raise ValueError("selection contains duplicate original photos")
    if not record["selected"]:
        raise ValueError("no frozen original images in selection")
    sample_by_proposal = {}
    for row in journal.category_records("observation", "score_review_sample"):
        p = row.data["payload"]
        proposal_id = p.get("proposal_id")
        if proposal_id in sample_by_proposal:
            raise ValueError("conflicting duplicate review sample")
        sample_by_proposal[proposal_id] = row
    annotations = journal.category_records("observation", "score_human_annotation")
    superseded = {a.data["payload"].get("supersedes") for a in annotations}
    statuses = {}
    for status in journal.category_records("observation", "score_review_status"):
        p = status.data["payload"]
        statuses[p.get("proposal_id")] = p
    already = attested_photo_annotation_ids(journal)
    candidates = []
    skipped = Counter()
    possible_reviewers = set()
    for row in annotations:
        a = row.data["payload"]
        sample = sample_by_proposal.get(a.get("proposal_id"))
        if sample is None:
            skipped["not_this_sampler_batch"] += 1
            continue
        proposal = journal.get(a["proposal_id"])
        p = proposal.data["payload"]
        image_sha = p.get("artifact", {}).get("sha256")
        original = original_images.get(image_sha)
        if (original is None or
                p.get("context", {}).get("sampler_manifest_sha256") != selection_sha or
                p.get("partition") !=
                  {"train": "training", "val": "validation", "test": "final"}.get(original["role"]) or
                sample.data["payload"].get("source_image_sha256") != image_sha or
                sample.data["payload"].get("role") != original["role"]):
            skipped["different_batch_or_provenance"] += 1
            continue
        if row.id in superseded:
            skipped["superseded_review"] += 1
            continue
        status = statuses.get(a["proposal_id"], {})
        if status.get("status") not in ("corrected", "confirmed", "unreadable"):
            skipped["not_a_completed_photo_review"] += 1
            continue
        if (a.get("verdict") not in ("correct", "confirm", "unreadable")
                or a.get("artifact_sha256") != image_sha
                or a.get("source_episode") != p.get("source_episode")
                or p.get("synthetic") is True):
            skipped["invalid_annotation_or_fixture"] += 1
            continue
        possible_reviewers.add(a["annotator"])
        if reviewer is not None and a["annotator"] != reviewer:
            skipped["other_reviewer"] += 1
            continue
        if a.get("independence_attested") is True or row.id in already:
            skipped["already_photo_attested"] += 1
            continue
        try:
            ScoreObserver.review_artifact(journal, p)
        except (OSError, ValueError):
            skipped["original_photo_missing_or_modified"] += 1
            continue
        candidates.append(dict(
            annotation_id=row.id, proposal_id=proposal.id,
            sample_id=sample.id, reviewer=a["annotator"],
            original_reviewed_at=a.get("reviewed_at"),
            verdict=a["verdict"], value=a.get("value"), role=original["role"],
            artifact_sha256=image_sha, source_episode=a["source_episode"]))
    return dict(candidates=candidates, reviewers=sorted(possible_reviewers),
                skipped=dict(skipped), frozen_manifest_sha256=selection_sha)


def attest(journal, manifest, *, reviewer=None, apply=False):
    plan = preview(journal, manifest, reviewer=reviewer)
    reviewer_names = {item["reviewer"] for item in plan["candidates"]}
    if reviewer is None and len(reviewer_names) > 1 and apply:
        raise ValueError("multiple original reviewers; specify --reviewer to attest only your own submissions")
    if reviewer is not None and plan["reviewers"] and reviewer not in plan["reviewers"]:
        raise ValueError("requested reviewer is not present in this frozen batch")
    counts = Counter(item["role"] for item in plan["candidates"])
    appended = []
    if apply:
        with journal.batch():
            for item in plan["candidates"]:
                annotation = journal.get(item["annotation_id"])
                proposal = journal.get(item["proposal_id"])
                # Re-check from the same source snapshot inside the atomic
                # append-only batch, never edit past review or image data.
                p = proposal.data["payload"]
                ScoreObserver.review_artifact(journal, p)
                payload = dict(category=CATEGORY, schema=SCHEMA,
                    annotation_id=annotation.id,
                    proposal_id=proposal.id, artifact_sha256=item["artifact_sha256"],
                    annotator=item["reviewer"],
                    original_reviewed_at=item["original_reviewed_at"],
                    attested_at=datetime.now(timezone.utc).isoformat(),
                    photo_read_confirmed=True,
                    asserted_scope="I independently read the original photograph when I submitted this score review",
                    retrospective=True, source_selection_sha256=plan["frozen_manifest_sha256"],
                    qualification="later human photo-reading attestation, NOT original checkbox, second reviewer, independent game, final-score certificate or new label",
                    physical_authorization=False)
                saved=journal.append("observation", payload,
                    episode=item["source_episode"],
                    sources=[item["proposal_id"],item["annotation_id"],item["sample_id"]],
                    producer="human-score-review-retrospective-attestation",
                    version="1")
                appended.append(saved.id)
    return dict(
        scope="existing reviewed original photographs from one immutable screenshot-selection batch",
        reviewer=reviewer or (next(iter(reviewer_names)) if len(reviewer_names)==1 else None),
        reviewers_seen=plan["reviewers"],
        eligible_for_retrospective_photo_attestation=len(plan["candidates"]),
        candidates_by_partition=dict(counts),
        skipped=plan["skipped"],
        appended_attestation_ids=appended,
        status="APPENDED — original reviews unchanged" if apply else "DRY RUN — NO WRITES",
        human_score_numbers_rewritten=False,
        complete_game_or_ala_learning_proven=False)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--journal", type=Path, required=True,
                    help="isolated, previously labeled screenshot review journal")
    ap.add_argument("--manifest", type=Path, required=True,
                    help="unchanged frozen selection used for those screenshots")
    ap.add_argument("--reviewer",
                    help="exact existing reviewer name; mandatory if batch has multiple reviewers")
    ap.add_argument("--attest-photo-reading", action="store_true",
                    help="operator explicitly confirms that they read these original photographs when submitting the existing reviews; appends dated records")
    args=ap.parse_args()
    path=args.journal.expanduser().resolve(strict=True)
    if (path.parent.joinpath("capture-manifest.json").exists()
            or ".local" in path.parts or "robotron-runs" in path.parts
            or not path.name.endswith(".sqlite3")):
        ap.error("use an isolated copied working score-review .sqlite3, not Charlie's original store")
    journal=EvidenceJournal(path,read_only=not args.attest_photo_reading)
    try:
        result=attest(journal,args.manifest,reviewer=args.reviewer,
                      apply=args.attest_photo_reading)
    finally:
        journal.close()
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
