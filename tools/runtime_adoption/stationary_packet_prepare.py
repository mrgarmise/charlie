"""Unsigned, read-only evidence inspection plus isolated review drafts.

This code never asserts a native gate, CI suite, or restore passed based solely
on file presence. It never writes into the controller's active packet root.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from .promotion import load
from .stationary import A, CANDIDATE, BASELINE, SCOPES, ORIGINAL, ROOT, evidence, sha
from .inventory import git


def _safe_measurement(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        return None
    try:
        return {"path": str(path.resolve(strict=True)), "sha256": sha(path)}
    except (OSError, ValueError):
        return None


def _record_candidate(path):
    m = _safe_measurement(path)
    if m:
        return m
    return {"path": str(path), "missing": True}


def _save_new(path, data):
    """Create and fsync one exclusive file. Never overwrite a prior review."""
    payload = (json.dumps(data, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return _safe_measurement(path)


def prepare(ctl):
    # Do not mutate either worktree, active packet or any operational control.
    ctl.preserved()
    if sha(ctl.normal) != ORIGINAL:
        raise ValueError("review drafts require unchanged original normal launcher")
    if git(ROOT, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("review controller checkout has uncommitted changes")
    controller = git(ROOT, "rev-parse", "HEAD")
    report = {
        "schema": "charlie-stationary-unsigned-review-draft-v1",
        "status": "PENDING_REVIEW",
        "release_approved": False,
        "native_gate_passes_issued": False,
        "ci_success_claimed": False,
        "created_at": time.time(),
        "identities": {
            "candidate": CANDIDATE, "baseline": BASELINE,
            "controller_sha": controller,
            "controller_tree": git(ROOT, "rev-parse", "HEAD^{tree}"),
            "normal_launcher": _safe_measurement(ctl.normal),
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        },
        "evidence": {},
        "gaps": [],
    }
    evidence_files = report["evidence"]
    original = ctl.home / "charlie-candidate-acceptance/20261116T160554Z/session.log"
    original_exit = original.parent / "exit-code.txt"
    guarded = ctl.ops / "logs/20261119T222200Z-batch-a-stationary.log"
    pre = sorted((ctl.review / "measurements").glob("native-pre-review-*.json")) if (ctl.review / "measurements").is_dir() else []
    evidence_files["native_pre_review"] = [_record_candidate(x) for x in pre]
    for name, path in (("original_229", original), ("original_exit", original_exit),
                       ("guarded_354", guarded)):
        evidence_files[name] = _record_candidate(path)
    qual_logs = sorted((ctl.ops / "logs").glob("stationary-qualification-*.log"))
    successes = []
    model = load(ctl.models)["objects"]["sha256"]
    for path in qual_logs:
        record = _record_candidate(path)
        if "sha256" in record:
            try:
                parsed = evidence(path, None, model)
                record.update({"observations": parsed["observations"],
                               "source": parsed["source"],
                               "clean_shutdown_logged": parsed["clean_shutdown_logged"],
                               "application_log_valid": True})
                successes.append(record)
            except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
                record["application_log_valid"] = False
                record["error"] = str(exc)
        evidence_files.setdefault("qualification_logs", []).append(record)
    evidence_files["prior_restore"] = _record_candidate(ctl.home / "charlie-restore-report.json")
    evidence_files["reviewer_key"] = _record_candidate(Path("/etc/charlie/stationary-reviewer.pem"))
    evidence_files["original_consultation"] = _record_candidate(ctl.ops / "run-historical-consultation.py")
    evidence_files["state"] = {
        "original_notebook": _record_candidate(ctl.ops / "state/learning-evidence.sqlite3"),
        "batch_a_notebook": _record_candidate(ctl.ops / "batch-a-state/learning-evidence.sqlite3"),
    }
    manifests = []
    for root in sorted((ctl.ops / "promotion-backups").glob("stationary-*/snapshot")):
        paths = (root / "state/backup-manifest.json",
                 root / "batch-a-state/backup-manifest.json",
                 root / "controls/manifest.json")
        if all(p.is_file() and not p.is_symlink() for p in paths):
            manifests.append([_safe_measurement(p) for p in paths])
    evidence_files["restore_manifests"] = manifests
    for label, needed in (("native pre-review", pre), ("native qualification with observations", successes),
                          ("three-file restore manifest set", manifests)):
        if not needed:
            report["gaps"].append(label + ": MISSING")
    report["gaps"] += [
        "N0: independent privileged owner, firmware, interpreter, alternate authority and device review",
        "N1: reviewer must check Pico display/ACK, STOP behavior, resource telemetry, camera and wire restrictions; initial tee cleanup was interrupted",
        "N2: verify state retention, candidate manual consultation regression and complete restore compatibility",
        "N5: explicit human review of exact controller and scope, then independent signatures",
        "CI: current exact-controller Actions run results, completed timestamps and immutable test artifact digests must be independently verified",
        "Restore: prior rehearsal independent_review=false; full-scope restore and compatibility decision required",
        "Do not create active ci.json, inputs.json, signed release or gate receipts until reviewed",
    ]
    # A draft records *references*, never successful gate claims. The exact
    # controller SHA is supplied; approval must bind the final revision later.
    templates = {}
    for gate in SCOPES[A]:
        templates[gate] = {
            "ability": A, "gate": gate,
            "candidate": CANDIDATE, "controller_sha": controller,
            "status": "pending", "independent_review": False,
            "artifacts": {},
            "review_questions": [gap for gap in report["gaps"] if gap.startswith(gate + ":")],
        }
    parent = ctl.review / "drafts"
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory = Path(tempfile.mkdtemp(prefix="unsigned-", dir=parent))
    os.chmod(directory, 0o700)
    files = {}
    files["report"] = _save_new(directory / "evidence-report.json", report)
    for gate, row in templates.items():
        files[gate] = _save_new(directory / ("draft-" + gate + ".json"), row)
    # No CI receipt files are created: GitHub artifacts must be verified, not
    # guessed from a success flag or test summary.
    return {
        "status": "UNSIGNED_DRAFT_ONLY",
        "directory": str(directory),
        "controller": controller,
        "normal_runtime_changed": False,
        "approval_issued": False,
        "artifact_files": files,
        "validated_native_sessions": len(successes),
        "review_gaps": report["gaps"],
    }
