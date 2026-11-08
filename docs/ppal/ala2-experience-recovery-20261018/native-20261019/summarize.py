from pathlib import Path
import sqlite3,json,hashlib,collections
R=Path('/home/five/ala2-recovery-20261019')
def connect(p):return sqlite3.connect(p.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ids(p):
    c=connect(p)
    try:return {r[0] for r in c.execute('select id from records')}
    finally:c.close()
baseline=R/'preserved/primary/learning-evidence.sqlite3';overnight=R/'preserved/overnight/learning-evidence.sqlite3';final=R/'checkpoint-evaluation/state/learning-evidence.sqlite3'
before=sha(final); base_ids=ids(baseline);night_ids=ids(overnight);final_ids=ids(final)
assert base_ids <= night_ids <= final_ids
summary=dict(primary_records=len(base_ids),overnight_records=len(night_ids),final_records=len(final_ids),
    primary_sha256=sha(baseline),overnight_sha256=sha(overnight),final_sha256=before,
    all_primary_and_overnight_ids_retained=True,new_record_count=len(final_ids-night_ids),
    native_disarmed=True,physical_policy_activated=False)
c=connect(final)
new_records=[]
for identifier,category,op,kind,producer in c.execute("select id,json_extract(document,'$.payload.category'),json_extract(document,'$.payload.op'),json_extract(document,'$.kind'),json_extract(document,'$.producer') from records"):
    if identifier not in night_ids:new_records.append(dict(id=identifier,category=category,op=op,kind=kind,producer=producer))
summary['new_categories']=dict(collections.Counter(r['category'] or r['op'] or r['kind'] for r in new_records))
summary['new_record_index']=new_records
summary['meditations']=[]
for identifier,text in c.execute("select id,document from records where json_extract(document,'$.payload.category')='normal_meditation_result'"):
    d=json.loads(text);summary['meditations'].append(dict(id=identifier,**d['payload'],new_this_run=identifier not in night_ids,overnight_addition=identifier in night_ids-base_ids))
summary['ingestions']=[]
for identifier,text in c.execute("select id,document from records where json_extract(document,'$.payload.category')='retrospective_ingestion'"):
    d=json.loads(text);summary['ingestions'].append(dict(id=identifier,**d['payload'],new_this_run=identifier not in night_ids))
controls=[]
path=R/'checkpoint-evaluation/executive-controls.jsonl'
if path.exists():
    for line in path.read_text().splitlines():
        r=json.loads(line);before_rows={a['project_id']:a for a in r['before']['alternatives']};after_rows={a['project_id']:a for a in r['actual_after_reload']['alternatives']}
        changes=[dict(project_id=i,before=before_rows[i]['score'],after=after_rows[i]['score'],
            before_units=before_rows[i]['experience_basis']['independent_units'],after_units=after_rows[i]['experience_basis']['independent_units'])
            for i in before_rows.keys() & after_rows.keys() if before_rows[i]['score']!=after_rows[i]['score']]
        controls.append(dict(project_id=r['project_id'],resolution_id=r['resolution']['resolution_id'],result=r['resolution'].get('result'),
            reason=r['resolution'].get('reason'),same_opportunity_set=before_rows.keys()==after_rows.keys(),
            changes=changes,actual_later_choice=r['actual_after_reload']['project']['id'] if r['actual_after_reload']['project'] else None))
summary['executive_controls']=controls
c.close();assert sha(final)==before
(R/'native-summary.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
print({k:v for k,v in summary.items() if k not in ('new_record_index','meditations','ingestions')})
