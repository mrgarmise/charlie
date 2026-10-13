"""Evaluate causal live Robotron shadow predictions against the next observation."""
from __future__ import annotations
import argparse, json, math, statistics
from pathlib import Path

def dist(a,b): return math.hypot(float(a[0])-float(b[0]), float(a[1])-float(b[1]))

def _objects(pred):
    d={}
    for kind in ("targets","threats"):
        for x in pred.get(kind,[]):
            d[(kind,x["id"])]=x
    return d

def evaluate(report):
    steps=report.get("steps", [])
    skipped=0
    shadow=[s for s in steps if isinstance(s.get("shadow"),dict)]
    diffs=sum(bool(s["shadow"].get("differs")) for s in shadow)
    samples=[]
    by_type={"player":[], "targets":[], "threats":[]}
    # Only adjacent ticks: t prediction is judged by genuinely later t+1 evidence.
    for a,b in zip(steps,steps[1:]):
        if b.get("tick") != a.get("tick", -99)+1: continue
        sa=a.get("shadow"); sb=b.get("shadow")
        if not isinstance(sa,dict) or not isinstance(sb,dict): continue
        pa=sa.get("prediction"); pb=sb.get("prediction")
        if not isinstance(pa,dict) or not isinstance(pb,dict):
            skipped += 1; continue
        if a.get('self_track_id') != b.get('self_track_id'):
            skipped += 1; continue
        horizon = pa.get('horizon_seconds')
        if horizon is not None:
            ta,tb = pa.get('observed_at'),pb.get('observed_at')
            if (not all(isinstance(t,(int,float)) and math.isfinite(t) for t in (ta,tb,horizon))
                    or horizon <= 0 or abs((tb-ta)-horizon) > max(.025,horizon*.25)):
                skipped += 1; continue
        elif pa.get('horizon_ticks',1) != 1:
            skipped += 1; continue
        row={"tick":a["tick"],"player":[],"objects":[]}
        pe=dist(pa["player_predicted"], pb["player_now"])
        base=dist(pa["player_now"], pb["player_now"])
        item={"kind":"player","predicted_error":pe,"baseline_error":base}
        samples.append(item); by_type["player"].append(item)
        nxt=_objects(pb)
        for kind in ("targets","threats"):
            for x in pa.get(kind,[]):
                y=nxt.get((kind,x["id"]))
                if y is None: continue
                item={"kind":kind,"id":x["id"],
                      "predicted_error":dist(x["predicted"],y["now"]),
                      "baseline_error":dist(x["now"],y["now"])}
                samples.append(item); by_type[kind].append(item)
    def summary(xs):
        if not xs: return {"n":0}
        p=[x["predicted_error"] for x in xs]; b=[x["baseline_error"] for x in xs]
        wins=sum(x["predicted_error"] < x["baseline_error"]-1e-9 for x in xs)
        ties=sum(abs(x["predicted_error"]-x["baseline_error"]) <= 1e-9 for x in xs)
        return {"n":len(xs),
                "prediction_median":round(statistics.median(p),3),
                "baseline_median":round(statistics.median(b),3),
                "prediction_mean":round(statistics.mean(p),3),
                "baseline_mean":round(statistics.mean(b),3),
                "wins":wins,"ties":ties,"losses":len(xs)-wins-ties,
                "win_rate":round(100*wins/len(xs),1)}
    return {
      "schema":"charlie-robotron-shadow-evaluation-v1",
      "objective_note":"Prediction metrics are diagnostic; game SCORE is the primary performance objective.",
      "skipped_incompatible_pairs":skipped,
      "limitations":"Diagnostics only: observations may contain tracking errors; no score or causal policy improvement claim.",
      "steps":len(steps),"shadow_steps":len(shadow),
      "disagreements":diffs,
      "disagreement_rate":round(100*diffs/len(shadow),1) if shadow else 0,
      "all":summary(samples),
      "player":summary(by_type["player"]),
      "targets":summary(by_type["targets"]),
      "threats":summary(by_type["threats"]),
    }

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report",type=Path)
    ap.add_argument("--output",type=Path)
    a=ap.parse_args()
    r=evaluate(json.loads(a.report.read_text()))
    out=a.output or a.report.with_name("shadow-evaluation.json")
    out.write_text(json.dumps(r,indent=2)+"\n")
    print(f"SHADOW: {r['shadow_steps']}/{r['steps']} steps; disagreements={r['disagreements']} ({r['disagreement_rate']}%)")
    for k in ("all","player","targets","threats"):
        s=r[k]
        if s["n"]:
            print(f"{k.upper()}: n={s['n']} pred median={s['prediction_median']} baseline={s['baseline_median']} wins={s['win_rate']}%")
        else: print(f"{k.upper()}: n=0")
    print(f"Evidence: {out}")

if __name__=="__main__":
    main()
