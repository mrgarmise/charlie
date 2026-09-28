"""Post-game Robotron reflection using Charlie's existing durable memory system.

Consumes one replay directory, compares the episode with prior locally evaluated
Charlie memories (and MARM recall when available), forms selected experiences,
and writes a small question queue for uncertainties worth human review.

This is analysis only: it imports no controller and never changes live policy.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from memory.former import Experience
from memory.gateway import MemoryGateway
from memory.marm import MarmWriteError

DEFAULT_QUESTIONS = Path.home() / ".local/share/charlie/robotron-questions.jsonl"


def _load(path):
    return json.loads(Path(path).read_text())


def _percent(n, d):
    return 0.0 if not d else 100.0 * n / d


def analyze(summary, rows, tracks):
    """Derive conservative episode observations; do not infer game outcomes."""
    frames = int(summary.get("frames", 0))
    decisions = int(summary.get("decision_frames", 0))
    unknown = int(summary.get("self_unknown_frames", 0))
    reacq = int(summary.get("self_reacquisitions", 0))
    action_counts = {
        (a.get("move"), a.get("fire")): int(a.get("count", 0))
        for a in summary.get("actions", [])
    }
    stay_none = action_counts.get(("STAY", "NONE"), 0)

    target_frames = sum(bool(r.get("targets")) for r in rows if r.get("status") == "decision")
    threat_frames = sum(bool(r.get("threats")) for r in rows if r.get("status") == "decision")

    observations = {
        "frames": frames,
        "decisions": decisions,
        "self_unknown_frames": unknown,
        "self_unknown_pct": round(_percent(unknown, frames), 1),
        "self_reacquisitions": reacq,
        "stay_none_frames": stay_none,
        "stay_none_pct_of_decisions": round(_percent(stay_none, decisions), 1),
        "target_frames": target_frames,
        "target_pct_of_decisions": round(_percent(target_frames, decisions), 1),
        "threat_frames": threat_frames,
        "threat_pct_of_decisions": round(_percent(threat_frames, decisions), 1),
        "visual_tracks": len(tracks),
    }

    findings = []
    if unknown:
        findings.append(("self_uncertainty",
                         f"SELF was unknown for {unknown}/{frames} frames "
                         f"({observations['self_unknown_pct']:.1f}%)."))
    if reacq:
        findings.append(("self_reacquisition",
                         f"SELF required {reacq} replay reacquisitions."))
    if decisions and stay_none:
        findings.append(("inaction",
                         f"Charlie chose STAY/NONE on {stay_none}/{decisions} decision frames "
                         f"({observations['stay_none_pct_of_decisions']:.1f}%)."))
    if decisions:
        findings.append(("perception_coverage",
                         f"Targets appeared on {target_frames}/{decisions} decision frames and "
                         f"threats on {threat_frames}/{decisions}."))
    return observations, findings


def _prior_local(gateway, limit=30):
    return gateway.evaluator.recent(limit=limit)


def _prior_remote(gateway, query):
    try:
        return gateway.recall(query, limit=10)
    except MarmWriteError:
        return []


def _occurrences(prior, phrase):
    needle = phrase.lower()
    return sum(needle in item.get("text", "").lower() for item in prior)


def _queue_question(path, question):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                existing.add(json.loads(line).get("id"))
            except (ValueError, TypeError):
                pass
    if question["id"] in existing:
        return False
    with path.open("a") as stream:
        stream.write(json.dumps(question, ensure_ascii=False) + "\n")
    return True


def reflect(replay_dir, gateway=None, questions_path=DEFAULT_QUESTIONS):
    replay_dir = Path(replay_dir)
    summary = _load(replay_dir / "summary.json")
    rows = _load(replay_dir / "replay.json")
    track_doc = _load(replay_dir / "tracks.json")
    tracks = track_doc.get("tracks", [])

    gateway = gateway or MemoryGateway()
    prior = _prior_local(gateway)
    remote = _prior_remote(
        gateway,
        "Robotron replay self tracking reacquisition perception decisions inaction")
    observations, findings = analyze(summary, rows, tracks)

    recording = str(summary.get("recording") or replay_dir)
    episode_key = recording.replace("/", "_")
    source = "ppal:robotron-reflection"

    promoted = []
    for category, text in findings:
        prior_count = _occurrences(prior, category.replace("_", " "))
        recurring = prior_count > 0
        event = Experience(
            kind="observation",
            summary=text,
            source=source,
            subject=category,
            confidence=1.0,
            novelty=not recurring,
            significant=recurring or category in ("self_uncertainty", "inaction"),
            tags=("robotron", "reflection", category),
            evidence=f"robotron:{episode_key}:{category}",
        )
        if gateway.remember(event):
            promoted.append(category)

    questions = []
    # Questions are deliberately about interpretation/teaching, not facts the
    # replay can settle by counting its own evidence.
    if observations["stay_none_pct_of_decisions"] >= 50:
        qid = f"robotron:{episode_key}:inaction-meaning"
        questions.append({
            "id": qid,
            "status": "open",
            "category": "strategy",
            "recording": recording,
            "question": (
                f"I chose STAY/NONE on {observations['stay_none_frames']}/"
                f"{observations['decisions']} decision frames "
                f"({observations['stay_none_pct_of_decisions']:.1f}%). "
                "When we review representative frames, should those be genuine "
                "wait decisions, or evidence that I failed to perceive something actionable?"
            ),
            "evidence": str(replay_dir / "replay.json"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    if observations["self_unknown_pct"] >= 15 or observations["self_reacquisitions"] >= 3:
        qid = f"robotron:{episode_key}:self-identity"
        questions.append({
            "id": qid,
            "status": "open",
            "category": "perception",
            "recording": recording,
            "question": (
                f"I lacked SELF for {observations['self_unknown_frames']} frames and "
                f"reacquired it {observations['self_reacquisitions']} times. "
                "I should first inspect those moments offline; if ambiguity remains, "
                "I may need you to identify which sprite is me."
            ),
            "evidence": str(replay_dir / "tracks.json"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    queued = sum(_queue_question(questions_path, q) for q in questions)

    result = {
        "schema": "charlie-robotron-reflection-v1",
        "recording": recording,
        "replay": str(replay_dir),
        "observations": observations,
        "findings": [{"category": c, "summary": t} for c, t in findings],
        "comparison": {
            "local_memories_considered": len(prior),
            "remote_memories_recalled": len(remote),
            "note": ("MARM recall is optional; local evaluator history remains usable "
                     "when MARM is unavailable."),
        },
        "memory": {"promoted_categories": promoted},
        "questions": questions,
        "new_questions_queued": queued,
    }
    (replay_dir / "reflection.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay_dir", type=Path)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    args = parser.parse_args()

    result = reflect(args.replay_dir, questions_path=args.questions)
    o = result["observations"]
    print(f"REFLECTION: {result['recording']}")
    print(f"SELF UNKNOWN: {o['self_unknown_frames']}/{o['frames']} "
          f"({o['self_unknown_pct']:.1f}%)")
    print(f"SELF REACQUISITIONS: {o['self_reacquisitions']}")
    print(f"STAY/NONE: {o['stay_none_frames']}/{o['decisions']} decisions "
          f"({o['stay_none_pct_of_decisions']:.1f}%)")
    print(f"PRIOR LOCAL MEMORIES: {result['comparison']['local_memories_considered']}")
    print(f"REMOTE RECALLS: {result['comparison']['remote_memories_recalled']}")
    print(f"MEMORIES PROMOTED: {len(result['memory']['promoted_categories'])}")
    print(f"NEW QUESTIONS: {result['new_questions_queued']}")
    print(f"Reflection: {args.replay_dir / 'reflection.json'}")
    print(f"Question queue: {args.questions.expanduser()}")


if __name__ == "__main__":
    main()
