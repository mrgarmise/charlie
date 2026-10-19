from pathlib import Path
import json, sqlite3, hashlib, math, collections
R=Path('/home/five/ala2-recovery-20261019')
ledger=json.loads((R/'tactical-diagnostics.json').read_text())['outcomes']
sources=json.loads((R/'tactical-sources.json').read_text())
records={};locations=collections.defaultdict(list);source_checks=[]
for s in sources:
    p=Path(s['path'])
    with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
    assert h==s['sha256']
    c=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True)
    for identifier,text in c.execute("select id,document from records where json_extract(document,'$.payload.category') in ('tactical_outcome','tactical_execution') or json_extract(document,'$.kind')='prediction'"):
        d=json.loads(text)
        if identifier in records:assert records[identifier]==d
        records[identifier]=d;locations[identifier].append(str(p))
    c.close();source_checks.append({'path':str(p),'sha256':h})
vectors={'N':(0,-1),'NE':(1,-1),'E':(1,0),'SE':(1,1),'S':(0,1),'SW':(-1,1),'W':(-1,0),'NW':(-1,-1)}
checks=[]
for row in ledger:
    outcome=records[row['evidence_id']];p=outcome['payload'];pred=records[row['prediction_id']];expected=pred['payload'].get('expected',pred['payload'])
    action=expected.get('actual_action',expected.get('selected'))
    delta=p['displacement'];v=vectors[row['move']];along=sum(a*b for a,b in zip(delta,v))/math.hypot(*v)
    checks.append(dict(evidence_id=row['evidence_id'],prediction_id=row['prediction_id'],episode=row['episode'],
        prediction_track=expected.get('self_track_id'),outcome_track=p['track_id'],
        same_track=expected.get('self_track_id')==p['track_id'],
        action_match=all(action[k]==row[k] for k in ('move','fire')),
        along_recomputed=along,along_matches=math.isclose(along,p['along'],abs_tol=1e-8),
        prediction_identity=expected.get('identity_status'),endpoint_identity=p['identity_status'],
        observation_id=p.get('observation_id'),observation_is_source=p.get('observation_id') in outcome['sources'],
        response_seconds=p['observed_at']-p['origin_at'],snapshot_paths=locations[row['evidence_id']]))
result=dict(source_snapshots=source_checks,retained_rows=len(ledger),origins=dict(collections.Counter(r['episode'] for r in ledger)),
    results=dict(collections.Counter(r['result'] for r in ledger)),checks=checks,
    unique_executions=sum(r['payload'].get('category')=='tactical_execution' for r in records.values()),
    unique_outcomes=sum(r['payload'].get('category')=='tactical_outcome' for r in records.values()),
    qualification='recorded same-track diagnostics; no independent identity or game qualification')
(R/'tactical-link-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print({k:v for k,v in result.items() if k not in ('checks','source_snapshots')})
print('track/action/along/source mismatches',[(r['evidence_id'],r['same_track'],r['action_match'],r['along_matches'],r['observation_is_source']) for r in checks if not all(r[k] for k in ('same_track','action_match','along_matches','observation_is_source'))])
