"""Measured live report comparison; missing timing stays unmeasured."""
import argparse
import json
from pathlib import Path
import statistics


def summarize(reports):
    groups={False:[],True:[]};intervals={False:[],True:[]}
    for report in reports:
        previous=None
        for row in report.get('steps',[]):
            state=row.get('viewer_state') or {};attached=state.get('attached')
            capture=row.get('capture_timestamp');execution=row.get('control_execution') or {}
            started=execution.get('started_at');checked=state.get('checked_at')
            if (type(attached) is not bool or capture is None or started is None or checked is None
                    or row.get('identity_status') not in ('provisional','confirmed')
                    or not 0 <= started-capture < 2 or abs(capture-checked)>1):
                previous=None;continue
            groups[attached].append((started-capture)*1000)
            if previous and previous[0]==attached and capture>previous[1]:
                intervals[attached].append(capture-previous[1])
            previous=(attached,capture)
    return {('attached' if flag else 'detached'):dict(samples=len(values),
        capture_to_controller_start_ms_mean=statistics.mean(values) if values else None,
        ordinary_action_cadence_hz=1/statistics.mean(intervals[flag]) if intervals[flag] else None)
        for flag,values in groups.items()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('reports',type=Path,nargs='+');args=ap.parse_args()
    print(json.dumps(dict(summary=summarize([json.loads(p.read_text()) for p in args.reports]),
        note='Observed ordinary-action cadence and sensor/capture-to-local-controller-start latency, not remote display onset. Scene/agency differences and demand-check lag confound causal attribution.'),indent=2))


if __name__=='__main__':main()
