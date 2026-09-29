"""Autonomous Robotron marathon orchestrator.

Each game remains an independent timestamped episode.  This module never
concatenates tracks, frames, or reports across game boundaries.

It wraps the known-good single-game player as a subprocess, retries START by
starting another independent attempt, evaluates completed live reports, and
enters per-episode/cross-episode meditation after repeated failure to establish
gameplay (normally exhausted credits).
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA="charlie-robotron-marathon-v1"

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def run(cmd):
    print("+", " ".join(map(str,cmd)), flush=True)
    return subprocess.run(cmd, check=False).returncode

def load_report(path):
    try: return json.loads(path.read_text())
    except (OSError, ValueError): return None

def established_gameplay(report):
    """Conservative: the existing player must actually have produced game steps."""
    if not report: return False
    steps=report.get("steps") or []
    return bool(report.get("armed") and report.get("acquisition") and
                any("action" in s for s in steps))

def safe_to_restart(report, returncode=0):
    """Only an explicit, evidenced terminal screen may authorize another START."""
    if returncode != 0 or not report:
        return False
    end = report.get('episode_end', {})
    return (end.get('state') == 'game_over' and end.get('confirmed') is True
            and bool(end.get('evidence')))


def write_session(path, doc):
    temporary = path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(doc,indent=2)+"\n")
    temporary.replace(path)

def meditate_session(session_dir, games):
    """Never merge games. Analyze each episode separately, then summarize metadata."""
    from .learning_review import review_session
    results=[]
    for game in games:
        g=Path(game["path"])
        report=g/"report.json"
        if report.exists():
            run([sys.executable,"-m","experiments.ppal.evaluate_robotron_shadow",str(report)])
        # Deep replay meditation is valid only if THIS episode owns tracks.json.
        if (g/"tracks.json").exists():
            run([sys.executable,"-m","experiments.ppal.meditate_robotron",str(g)])
        results.append({
            "path":str(g),
            "report":str(report) if report.exists() else None,
            "shadow_evaluation":str(g/"shadow-evaluation.json")
                if (g/"shadow-evaluation.json").exists() else None,
            "predictive_meditation":str(g/"predictive-reconstruction.json")
                if (g/"predictive-reconstruction.json").exists() else None,
        })
    summary={
      "schema":"charlie-robotron-marathon-meditation-v1",
      "created_at":datetime.now(timezone.utc).isoformat(),
      "rule":"Independent episodes only; no trajectory/frame/track concatenation.",
      "games":results,
    }
    p=session_dir/"meditation.json"
    p.write_text(json.dumps(summary,indent=2)+"\n")
    review_session(session_dir, games)
    print(f"MEDITATION COMPLETE: {p}")

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-games",type=int,default=50)
    ap.add_argument("--game-seconds",type=float,default=60.0,
                    help="safety horizon per current single-game runner")
    ap.add_argument("--failed-starts",type=int,default=2)
    ap.add_argument("--retry-wait",type=float,default=5.0)
    ap.add_argument("--focus",type=float,default=1.30,
                    help="manual camera lens position passed to each game")
    ap.add_argument("--root",type=Path,default=Path("robotron-runs"))
    ap.add_argument("--arm",action="store_true",help="required to send controls")
    a=ap.parse_args()
    import math
    if not 1 <= a.max_games <= 100: ap.error('--max-games must be 1..100')
    if not math.isfinite(a.game_seconds) or not 1 <= a.game_seconds <= 3600:
        ap.error('--game-seconds must be 1..3600')
    if not 1 <= a.failed_starts <= 10: ap.error('--failed-starts must be 1..10')
    if not math.isfinite(a.retry_wait) or not 0 <= a.retry_wait <= 60:
        ap.error('--retry-wait must be 0..60')
    if not a.arm: ap.error("--arm is required for an autonomous marathon")
    session=a.root/f"marathon-{stamp()}"
    session.mkdir(parents=True,exist_ok=False)
    doc={"schema":SCHEMA,"started_at":datetime.now(timezone.utc).isoformat(),
         "status":"running","rule":"games remain independent","games":[],"failed_starts":[]}
    write_session(session/"session.json",doc)

    failures=0
    try:
        while len(doc["games"]) < a.max_games:
            game=a.root/f"play-{stamp()}"
            # Avoid same-second collision without ever reusing an episode directory.
            while game.exists():
                time.sleep(1.05); game=a.root/f"play-{stamp()}"
            rc=run([sys.executable,"-m","experiments.ppal.play_robotron",
                    "--arm","--seconds",str(a.game_seconds),
                    "--focus",str(a.focus),"--output",str(game)])
            report=load_report(game/"report.json")
            if established_gameplay(report):
                failures=0
                entry={"path":str(game),"returncode":rc,
                       "result":report.get("result"),"ticks":report.get("ticks"),
                       "score":None,"score_status":"pending"}
                doc["games"].append(entry)
                run([sys.executable,"-m","experiments.ppal.evaluate_robotron_shadow",
                     str(game/"report.json")])
                write_session(session/"session.json",doc)
                # Current player has a safety horizon. If it timed out while gameplay
                # was active, do NOT press START: that could spend a credit mid-game.
                if report.get("result")=="TIME LIMIT":
                    print("GAMEPLAY HIT SAFETY HORIZON; stopping marathon rather than risking START mid-game.")
                    doc["status"]="safety_horizon"
                    break
                if not safe_to_restart(report, rc):
                    doc['status'] = 'needs_episode_end_review'
                    print('STOP: tracking loss is not confirmed game over; no further START.')
                    break
                print("Confirmed game over; preparing next START.")
                time.sleep(a.retry_wait)
                continue

            failures += 1
            doc["failed_starts"].append({"path":str(game),"returncode":rc,
                                         "at":datetime.now(timezone.utc).isoformat()})
            write_session(session/"session.json",doc)
            print(f"NO GAMEPLAY after START attempt {failures}/{a.failed_starts}")
            if not safe_to_restart(report, rc):
                doc['status'] = 'unverified_start_or_episode_end'
                break
            if failures >= a.failed_starts:
                doc["status"]="credits_exhausted_or_gameplay_unavailable"
                break
            time.sleep(a.retry_wait)
    except KeyboardInterrupt:
        doc["status"]="interrupted"
    finally:
        if doc["status"]=="running": doc["status"]="max_games_reached"
        doc["ended_at"]=datetime.now(timezone.utc).isoformat()
        write_session(session/"session.json",doc)
        print(f"MARATHON ENDED: {doc['status']}; games={len(doc['games'])}")
        print("ENTERING MEDITATION")
        meditate_session(session,doc["games"]+doc["failed_starts"])

if __name__=="__main__":
    main()
