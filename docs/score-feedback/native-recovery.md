# Read-only recovery and acceptance handoff

No hardware deployment or physical operation is authorized by these instructions. The first procedure uses only the Pi's existing Python and SQLite; it exports preserved records/images without changing either original notebook. No application stop, gameplay, camera capture, servo movement or policy activation is requested.

## Export the original October 10 store

On Charlie, run the following with the existing interpreter. The destination must be new. SQLite's read-only backup includes committed WAL records; copying just the database file while a reviewer is active would not guarantee that.

```bash
PYTHON=/home/five/Projects/charlie/.venv/bin/python
OUT="/home/five/Projects/charlie/score-feedback-export-$(date -u +%Y%m%dT%H%M%SZ)"
export OUT
"$PYTHON" - <<'PY'
import collections, hashlib, json, os, shutil, sqlite3
from pathlib import Path
out=Path(os.environ['OUT']);out.mkdir(exist_ok=False)
original=Path('/home/five/.local/share/charlie/score-review/learning-evidence.sqlite3')
source=sqlite3.connect(original.as_uri()+'?mode=ro',uri=True)
copy=sqlite3.connect(out/'learning-evidence.sqlite3')
try:source.backup(copy)
finally:copy.close();source.close()
copy=sqlite3.connect((out/'learning-evidence.sqlite3').as_uri()+'?mode=ro',uri=True)
rows=[dict(sequence=s,id=i,document=d,committed_at=t) for s,i,d,t in copy.execute('SELECT sequence,id,document,committed_at FROM records ORDER BY sequence')]
copy.close()
for r in rows:
    if hashlib.sha256(r['document'].encode()).hexdigest()!=r['id']:raise ValueError('Original evidence digest mismatch')
data={r['id']:json.loads(r['document']) for r in rows}
annotations=[(i,d['payload']) for i,d in data.items() if d['payload'].get('category')=='score_human_annotation']
proposals={i:d['payload'] for i,d in data.items() if d['payload'].get('category')=='score_review_proposal'}
locations={};missing=[]
for key in sorted({a['proposal_id'] for _,a in annotations}):
    p=proposals[key];expected=p['artifact']['sha256']
    candidates=[Path(q['artifact']['path']) for q in proposals.values() if q['artifact']['sha256']==expected]
    path=next((p for p in candidates if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==expected),None)
    if path is None:missing.append(dict(proposal_id=key,artifact=p['artifact']));continue
    folder=out/'images';folder.mkdir(exist_ok=True)
    dest=folder/(expected+path.suffix.lower());shutil.copyfile(path,dest)
    if hashlib.sha256(dest.read_bytes()).hexdigest()!=expected:raise ValueError('Copy hash mismatch')
    locations[expected]=str(dest.relative_to(out))
superseded={a.get('supersedes') for _,a in annotations}
active=[dict(id=i,**a) for i,a in annotations if i not in superseded]
statuses=[dict(id=i,**d['payload']) for i,d in data.items() if d['payload'].get('category')=='score_review_status']
consumed=None
normal=Path('/home/five/.local/share/charlie/development/learning-evidence.sqlite3')
if normal.is_file():
    c=sqlite3.connect(normal.as_uri()+'?mode=ro',uri=True)
    retained={r[0] for r in c.execute('SELECT id FROM records')};c.close()
    consumed=[i for i,_ in annotations if i in retained]
report=dict(source=str(original),records=rows,statuses=statuses,annotations=active,
    status_records=len(statuses),annotation_records=len(annotations),active_annotations=len(active),
    distinct_reviewed_proposals=len({a['proposal_id'] for a in active}),
    distinct_reviewed_images=len({a['artifact_sha256'] for a in active}),missing_images=missing,
    imported_annotation_ids=consumed,
    warning='An imported ID is not proof of reader training or subsequent inference',physical_authorization=False)
(out/'recovery.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'image-locations.json').write_text(json.dumps(locations,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('records','statuses','annotations')},indent=2))
PY
tar -czf "$OUT.tar.gz" -C "$(dirname "$OUT")" "$(basename "$OUT")"
printf '%s\n' "$OUT.tar.gz"
```

Return that archive for authentic examination. It preserves original IDs, documents, commit/review timestamps, supersession links, raw prediction and human values, image hashes, missing-image failures and possible import matches. Existing copied/recovered notebooks under `development/recovered-history` remain untouched. If the review store is missing, report that absence and search read-only:

```bash
find /home/five/.local/share/charlie /home/five/Projects/charlie /home/five/charlie-ala2-bae659f60b0e \
  -type f \( -name '*evidence.sqlite3' -o -name '*score*review*' -o -name 'score.jsonl' \) -print
```

Search notebooks by their actual `score_human_annotation` categories, not merely filenames. Do not relabel missing original images or infer successful ingestion from existence. Logs and handoff counts are leads, not replacement labels. The October 11 uploaded archive was examined and has zero human annotations.

## Controlled import, candidate development and independent comparison

Run these commands in a tested host checkout of the integration branch, after authentic export. Use a fresh **working** notebook; never pass the original Pi notebook as output. No fixture-admission switch exists in the production CLI.

```bash
python -m pip install -r requirements-score-review.txt
python -m experiments.ppal.inspect_robotron_score \
  --review-journal /new/working/learning-evidence.sqlite3 \
  --import-review-source /export/learning-evidence.sqlite3
python tools/score_feedback_candidate.py /new/working/learning-evidence.sqlite3 \
  --calibration /verified/calibration.json --training-partition diagnostic \
  --build /new/working/score-feedback-candidate.json
```

Diagnostic consultation is explicit and must be recorded as development/training exposure. It cannot later become an independent evaluation set. Training partitions are the default; original partition assignments cannot be silently rewritten. Store the emitted candidate ID and frozen state/artifact hashes. Check `excluded` for disputes, unreadable/missing images, missing channel binding, synthetic labels, partition overlap, calibration mismatch and digit-count mismatch. Empty candidates are not learning success.

For independent validation, use separately reviewed originals from nonoverlapping games/sessions/images, with immutable pre-review predictions and reader revision. Do not create a validation copy of a training frame or reuse adjacent correlated frames as independent physical captures. Acquire missing labels through the existing inspector/review interface, not generated answers. Use:

```bash
python tools/score_feedback_candidate.py /new/working/learning-evidence.sqlite3 \
  --calibration /verified/calibration.json --evaluate EXACT_CANDIDATE_ID --partition validation
python -m experiments.ppal.inspect_robotron_score /preserved/original.png \
  --calibration /verified/calibration.json
python -m experiments.ppal.inspect_robotron_score /preserved/original.png \
  --calibration /verified/calibration.json --feedback-candidate /new/working/score-feedback-candidate.json
```

The last two commands compare identical camera pixels with and without retained state. Restart the process and reload the artifact to check persistence. The candidate must also be checked against the current active annotation set: any superseding/disputed label invalidates its prior qualification and requires a new immutable candidate/evaluation. A diagnostic candidate is never silently installed into ScoreObserver, gameplay or PPAL. Live use remains subject to existing independent qualification/authorization/rollback pathways; this feature supplies no live activation adapter.

Record reviewed-example fit separately from unseen validation, numeric exact-match and canonical-string digit edit accuracy, unreadable false positives, high-confidence errors, abstention and regression on previously correct examples. Null/unknown scores are not zero. Performance-history certificates remain independently guarded and unavailable on master until their separate architecture is integrated; the UI reports unavailable qualification rather than inventing scores.

## Native cost and merge dependencies

Native offline testing of a new checkout requires separately approved staging; nothing was deployed in this mission. After approval, use `/usr/bin/time -v` around the same offline image replay/evaluation and retain native model size, process RSS, per-frame CPU/wall times, temperature, architecture, Python/OpenCV versions and exact revision. Include warm-up and repeated identical-frame replay without mixing host and Pi timings. Do not add gameplay or servo commands for benchmarking.

Merge remains blocked until the actual recovered labels and a valid persisted update are examined, with an authentic controlled recognition comparison and all remaining required checks/permissions verified. Human-feedback score-reader adaptation is separate from Executive E1, PPAL action-policy P1 and guarded Executive-to-PPAL I1 acceptance. No complete-game score, new physical action or ALA-2 completion follows from this milestone.
