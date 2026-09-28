"""Append-only Robotron performance ledger.

SCORE is the primary external objective. Diagnostic metrics explain score; they
do not replace it.
"""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "charlie-robotron-performance-v1"
DEFAULT = Path("robotron-runs/performance.jsonl")

def append_record(ledger: Path, report: Path, score: int, *, lives_used=None, note=None):
    if isinstance(score, bool) or not isinstance(score, int) or score < 0:
        raise ValueError('score must be a nonnegative integer')
    if lives_used is not None and (isinstance(lives_used,bool) or not isinstance(lives_used,int) or lives_used < 0):
        raise ValueError('lives_used must be a nonnegative integer')
    data = json.loads(report.read_text())
    rec = {
        "schema": SCHEMA,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "run": str(report.parent),
        "score": int(score),
        "objective": "maximize_score",
        "score_source": "human_reported",
        "episode_complete": data.get('episode_end',{}).get('confirmed') is True and data.get('episode_end',{}).get('state') == 'game_over',
        "policy_version": data.get('provenance',{}).get('git_commit'),
        "result": data.get("result"),
        "seconds": data.get("seconds"),
        "ticks": data.get("ticks"),
        "lives_used": lives_used,
        "note": note,
    }
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", type=Path)
    ap.add_argument("--score", type=int, required=True)
    ap.add_argument("--lives-used", type=int)
    ap.add_argument("--note")
    ap.add_argument("--ledger", type=Path, default=DEFAULT)
    a=ap.parse_args()
    rec=append_record(a.ledger,a.report,a.score,lives_used=a.lives_used,note=a.note)
    print(f"RECORDED SCORE: {rec['score']}  run={rec['run']}")
    print(f"Ledger: {a.ledger}")

if __name__=="__main__":
    main()
