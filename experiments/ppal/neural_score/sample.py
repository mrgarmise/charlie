"""Select preserved original Robotron HUD camera frames for human score review.

Read-only discovery from the canonical 2026-10-18 recording inventory and
score.jsonl source clock. No cameras, controls or live model. Optional --queue
writes review proposals to an explicitly isolated working journal, not sources.
The sampler NEVER uses Charlie's unverified prediction as a training label.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from ..eyes.calibration import Calibration
from ..robotron_hud import RobotronHUDReader

SCHEMA = "charlie-neural-score-sample-selection-v1"
SPLITS = {"train": "training", "val": "validation", "test": "final"}


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def role_for_group(group, seed):
    # Role assignment is based on recording-group identity, NEVER on score
    # predictions, training results or human annotations.
    n = int(hashlib.sha256((str(seed) + "|" + group).encode()).hexdigest()[:16], 16) / 16**16
    return "train" if n < .70 else "val" if n < .85 else "test"


def _source_directory(entry):
    # Treat duplicate original-home/restored-home directories as one candidate.
    paths = sorted(entry["paths"], key=lambda s: ("original-home" in s, len(s)))
    return next((Path(s).resolve() for s in paths if Path(s).is_dir()), None)


def _group(path):
    # Multiple game-XX recordings in the same marathon belong to one split.
    return str(path.parent if path.name.startswith("game-") else path)


def _reader_crop(image, reader):
    # Source-calibration must leave the entire extended score strip inside the
    # camera exposure; otherwise perspective extrapolation fabricates pixels.
    w, h = image.size
    tl, tr, br, bl = reader.calibration.corners
    ext_left = (tl[0] - .10 * (bl[0] - tl[0]), tl[1] - .10 * (bl[1] - tl[1]))
    ext_right = (tr[0] - .10 * (br[0] - tr[0]), tr[1] - .10 * (br[1] - tr[1]))
    if w < 320 or h < 180 or not all(0 <= x <= 1 and 0 <= y <= 1 for x, y in (ext_left, ext_right)):
        raise ValueError("missing full original camera HUD geometry")
    hud = reader.rectify(image)
    # Bright, textured score strips are useful candidates, but this is NOT
    # recognition truth. Empty HUDs remain recorded as exclusions for review.
    crop = hud.crop((int(640 * reader.P1_X[0]), 0, int(640 * reader.P1_X[1]), 96))
    gray = np.asarray(crop.convert("L").resize((32, 8)), dtype=np.float32)
    if float(np.percentile(gray, 99)) < 12:
        raise ValueError("score strip unilluminated or missing")
    return digest([int(x) for x in gray.flatten() // 24]), float(np.std(gray))


def discover(inventory, calibration, *, seed=17, scan_limit=6000, prior=()):
    entries = json.loads(Path(inventory).read_text())
    if not isinstance(entries, list):
        raise ValueError("canonical recording inventory must be an array")
    reader = RobotronHUDReader(calibration)
    commitments = {}
    for file in prior:
        old = json.loads(Path(file).read_text())
        if old.get("schema") != SCHEMA or digest({k: v for k, v in old.items() if k != "digest"}) != old.get("digest"):
            raise ValueError("prior frozen sampler manifest invalid")
        for row in old["selected"]:
            group, role = row["split_group"], row["role"]
            if group in commitments and commitments[group] != role:
                raise ValueError("prior session split collision")
            commitments[group] = role

    diagnostics = Counter()
    candidates = []
    already_seen = set()
    groups = {}
    for entry in sorted(entries, key=lambda x: x["canonical_game_id"]):
        game_id = entry["canonical_game_id"]
        root = _source_directory(entry)
        if root is None:
            diagnostics["missing_recording_directory"] += 1
            continue
        group = _group(root)
        role = commitments.get(group, role_for_group(group, seed))
        if group in groups and groups[group] != role:
            raise ValueError("one recording group would cross partitions")
        groups[group] = role
        logfile = root / "score.jsonl"
        if not logfile.is_file():
            diagnostics["no_score_source_log"] += 1
            continue
        before = file_sha(logfile)
        with logfile.open() as stream:
            for number, text in enumerate(stream, 1):
                if len(candidates) + diagnostics["scanned_frames"] >= scan_limit:
                    diagnostics["scan_cap_reached"] += 1
                    break
                try:
                    row = json.loads(text)
                    if row.get("score_partition") != "gameplay":
                        diagnostics["not_gameplay"] += 1
                        continue
                    name = row.get("raw_frame")
                    if not isinstance(name, str) or not name.startswith("score-raw-") or not name.endswith(".png"):
                        diagnostics["not_retained_score_original"] += 1
                        continue
                    path = (root / name).resolve()
                    if not path.is_relative_to(root) or not path.is_file():
                        diagnostics["missing_or_unsafe_frame"] += 1
                        continue
                    timestamp = row.get("timestamp", row.get("t"))
                    if type(timestamp) not in (int, float) or not math.isfinite(timestamp) or timestamp < 0:
                        diagnostics["no_authentic_capture_time"] += 1
                        continue
                    raw_sha = file_sha(path)
                    if raw_sha in already_seen:
                        diagnostics["duplicate_original_bytes"] += 1
                        continue
                    with Image.open(path) as img:
                        img.verify()
                    with Image.open(path) as img:
                        feature, contrast = _reader_crop(img.convert("RGB"), reader)
                    ch = row.get("p1", {})
                    if not isinstance(ch, dict):
                        ch = {}
                    proposed = ch.get("observed_score", ch.get("observed"))
                    if type(proposed) is not int or proposed < 0:
                        proposed = None
                    conf = ch.get("confidence", 0)
                    if type(conf) not in (int, float) or not math.isfinite(conf) or not 0 <= conf <= 1:
                        conf = 0.
                    diagnostics["scanned_frames"] += 1
                    already_seen.add(raw_sha)
                    candidates.append(dict(canonical_game_id=game_id, source_directory=str(root),
                        source_image=str(path), source_image_sha256=raw_sha, source_log_sha256=before,
                        source_log_line=number, source_timestamp=timestamp,
                        source_observation_id=row.get("observation_id"), role=role,
                        split_group=group, source_session=group,
                        proposed_score=proposed, proposed_confidence=float(conf),
                        score_status=ch.get("status", "unknown"), score_strip_fingerprint=feature,
                        contrast=contrast, selection_origin="recorded original score camera image; not a verified human label"))
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    diagnostics["invalid_or_unusable_frame"] += 1
                    continue
            if diagnostics["scan_cap_reached"]:
                break
        if file_sha(logfile) != before:
            raise RuntimeError("source score log changed during sampling")
    return candidates, diagnostics, groups


def select(candidates, *, seed=17, limit=300, per_game=18):
    if limit < 1 or per_game < 1:
        raise ValueError("positive bounded sampling limits required")
    grouped = defaultdict(list)
    for row in candidates:
        grouped[row["canonical_game_id"]].append(row)
    pool = []
    for game in sorted(grouped):
        seen = set()
        # Deterministic diversity: prefer uncertain/low-confidence predictions
        # but keep distinct score appearances and avoid near-duplicate HUDs.
        # No human truth enters this ranking.
        rank = sorted(grouped[game], key=lambda r: (
            0 if r["proposed_score"] is None else 1,
            r["proposed_confidence"],
            hashlib.sha256((str(seed) + r["source_image_sha256"]).encode()).hexdigest()))
        for row in rank:
            key = (row["score_strip_fingerprint"], row["proposed_score"])
            if key in seen:
                continue
            seen.add(key)
            pool.append(row)
            if len(seen) >= per_game:
                break
    # Interleave games, instead of letting one long recording take the queue.
    queue = defaultdict(list)
    for r in pool:
        queue[r["canonical_game_id"]].append(r)
    games = sorted(queue)
    chosen = []
    while games and len(chosen) < limit:
        for game in tuple(games):
            if len(chosen) >= limit:
                break
            if queue[game]:
                chosen.append(queue[game].pop(0))
            if not queue[game]:
                games.remove(game)
    return chosen


def freeze(inventory, calibration_path, output, *, seed=17, limit=300, per_game=18, prior=()):
    output = Path(output)
    if output.exists():
        raise FileExistsError("sampler output must be a new immutable file")
    calibration = Calibration.load(Path(calibration_path))
    candidates, diagnostics, groups = discover(inventory, calibration, seed=seed, prior=prior)
    chosen = select(candidates, seed=seed, limit=limit, per_game=per_game)
    record = dict(schema=SCHEMA, inventory_sha256=file_sha(inventory),
        calibration_sha256=file_sha(calibration_path), seed=seed, selection_limit=limit,
        per_game_limit=per_game, split_groups=groups,
        source_candidates=len(candidates), selected=chosen, exclusions=dict(diagnostics),
        meaning="source-linked screenshot review proposals, not score truth or complete games",
        prior_manifests=[file_sha(p) for p in prior])
    record["digest"] = digest(record)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
    return record


def queue_for_review(manifest, journal_path):
    # An operator must explicitly give a NEW isolated working-state location.
    # Never write into the game's preserved evidence or the default Pi notebook.
    from memory.evidence import EvidenceJournal, digest as evidence_digest
    from ..score_observer import ScoreObserver
    manifest = Path(manifest).resolve()
    record = json.loads(manifest.read_text())
    if record.get("schema") != SCHEMA or digest({k: v for k, v in record.items() if k != "digest"}) != record.get("digest"):
        raise ValueError("invalid frozen selection")
    journal_path = Path(journal_path).expanduser().resolve()
    if any(journal_path == Path(r["source_image"]).resolve()
           or journal_path.is_relative_to(Path(r["source_directory"]).resolve())
           for r in record["selected"]):
        raise ValueError("review journal must be outside all original recording trees")
    if "score-review" in journal_path.parts or "development" in journal_path.parts:
        raise ValueError("review journal must be a dedicated isolated working copy")
    journal = EvidenceJournal(journal_path)
    try:
        present = {
            r.data["payload"].get("source_image_sha256"): r
            for r in journal.category_records("observation", "score_review_sample")
        }
        counts = Counter()
        for item in record["selected"]:
            src = Path(item["source_image"])
            if file_sha(src) != item["source_image_sha256"]:
                raise ValueError("original source image changed")
            scorelog = Path(item["source_directory"]) / "score.jsonl"
            if file_sha(scorelog) != item["source_log_sha256"]:
                raise ValueError("original score log changed")
            if item["source_image_sha256"] in present:
                if present[item["source_image_sha256"]].data["payload"].get("role") != item["role"]:
                    raise ValueError("existing score review sample split conflict")
                counts["already_queued"] += 1
                continue
            role = item["role"]
            if role not in SPLITS:
                raise ValueError("invalid training/holdout role")
            source_episode = item["canonical_game_id"]
            at = item["source_timestamp"]
            source = journal.append("observation", dict(
                category="score_review_source", artifact=dict(path=str(src),sha256=item["source_image_sha256"]),
                original_observation_id=item["source_observation_id"], score_log_sha256=item["source_log_sha256"],
                score_log_line=item["source_log_line"], source_session=item["source_session"],
                note="archived source row, not fresh independent camera capture or human truth"),
                episode=source_episode, at=at, producer="score-frame-sampler", version="1")
            calibration = Calibration.load_by_digest if False else None
            # Compare the exact calibration identity from the frozen manifest;
            # the corpus adapter also enforces its geometric digest.
            proposal = ScoreObserver.review_proposal(journal,src,
                source_episode=source_episode,timestamp=at,clock="preserved score.jsonl exposure basis",
                source_id=source.id,proposed=item["proposed_score"],
                confidence=item["proposed_confidence"],partition=SPLITS[role],
                context=dict(source_session=item["source_session"],score_channel=1,
                    sampler_manifest_sha256=file_sha(manifest),
                    source_log_sha256=item["source_log_sha256"],
                    calibration_sha256=record["calibration_sha256"],
                    calibration_geometry_digest=item.get("calibration_geometry_digest"),
                    source_observation_id=item["source_observation_id"],
                    source_recording=item["canonical_game_id"]),
                synthetic=False)
            attempt = "score-frame-sample:" + digest(dict(source_image_sha256=item["source_image_sha256"], game=source_episode))
            item_record = journal.append("observation", dict(
                category="score_review_sample",sample=True,
                attempt_id=attempt,capture_key=attempt,source_root=item["source_directory"],
                source_episode=source_episode,session=item["source_session"],
                number="frame " + str(item["source_log_line"]), proposal_id=proposal.id,
                artifact=dict(path=str(src),sha256=item["source_image_sha256"]),
                additional_originals=[],role=role,report_sha256=None,
                source_image_sha256=item["source_image_sha256"],
                reported_score=None,reader_status=item["score_status"],
                complete_game_claim=False,
                result="sampled original HUD frame; not a complete-game claim",
                physical_authorization=False,original_score_observation_id=item["source_observation_id"]),
                episode=source_episode,at=at,sources=[proposal.id,source.id],
                producer="score-frame-sampler",version="1")
            present[item["source_image_sha256"]] = item_record
            counts["queued"] += 1
        return dict(**counts, review_journal=str(journal_path),
            original_evidence_modified=False, complete_game_qualified=False)
    finally:
        journal.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", type=Path, required=True,
                   help="canonical-game-manifest.json from read-only ALA2 inventory")
    p.add_argument("--calibration", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True,
                   help="new frozen selection JSON; never overwrite")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--limit", type=int, default=300)
    p.add_argument("--per-game", type=int, default=18)
    p.add_argument("--prior-manifest", type=Path, action="append", default=[])
    p.add_argument("--queue-to-working-journal", type=Path,
                   help="EXPLICIT opt-in isolated journal; no original score/learning journal")
    a = p.parse_args()
    if not 1 <= a.limit <= 2000 or not 1 <= a.per_game <= 64:
        p.error("sampler limits 1..2000 frames and 1..64 per game")
    record = freeze(a.inventory, a.calibration, a.output, seed=a.seed, limit=a.limit,
                    per_game=a.per_game, prior=a.prior_manifest)
    result = dict(selection_id=record["digest"], selected=len(record["selected"]),
                  candidates=record["source_candidates"], roles=dict(Counter(r["role"] for r in record["selected"])),
                  exclusions=record["exclusions"], original_state_modified=False,
                  authenticated_human_labels=0)
    if a.queue_to_working_journal:
        result["queue"] = queue_for_review(a.output, a.queue_to_working_journal)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
