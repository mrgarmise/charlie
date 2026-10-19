"""Fresh-process actual Executive selection with a scoped read-only ablation."""
from pathlib import Path
from copy import deepcopy
import sqlite3,json,sys,shutil,math
sys.path.insert(0,'/home/five/charlie-ala2-recovery-20261019')
from memory.evidence import EvidenceJournal,EvidenceRecord,digest
from memory.learning_projects import LearningExecutive
from memory.gateway import MemoryGateway
from memory.store import JsonlStore
from memory.evaluator import MemoryEvaluator
from learning.causal_audit import replay
R=Path('/home/five/ala2-recovery-20261019');source=R/'checkpoint-evaluation/state';state=R/'e1-fresh-process';state.mkdir()
control=json.loads((R/'checkpoint-evaluation/executive-controls.jsonl').read_text().splitlines()[0])
cutoff=4158
c=sqlite3.connect((source/'learning-evidence.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
rows=[EvidenceRecord(*r) for r in c.execute('SELECT sequence,id,document,committed_at FROM records WHERE sequence<=? ORDER BY sequence',(cutoff,))];c.close()
class Prefix:
    def records(self):return rows
    def verify(self):
        seen=set()
        for r in rows:
            d=r.data
            assert digest(d)==r.id and all(i in seen for i in d['sources'])
            seen.add(r.id)
j=EvidenceJournal(state/'learning-evidence.sqlite3');j.merge_from(Prefix());j.close();del rows
for name in ('evaluator.sqlite3','memory.jsonl'):
    shutil.copy2(source/name,state/name)
(R/'e1-prefix-ready').write_text('quiesced source copy finished\n')
j=EvidenceJournal(state/'learning-evidence.sqlite3')
gateway=MemoryGateway(store=JsonlStore(state/'memory.jsonl'),evaluator=MemoryEvaluator(state/'evaluator.sqlite3'))
try:
    executive=LearningExecutive(j,gateway)
    environment={k:set(v) if isinstance(v,list) else v for k,v in control['environment'].items()}
    projects=executive.projects();pid=control['project_id']
    # Actual invocation writes the ordinary selected event. No inspect/replay
    # substitutes for this later real evaluation.
    actual=executive.select(**environment)
    ablated=deepcopy(projects)
    prior=control['before']['project']['progress']
    for field in ('independent_offline_evidence_units','independent_physical_episodes'):
        ablated[pid]['progress'][field]=prior.get(field,0)
    counterfactual=replay(ablated,environment)
    old={a['project_id']:a for a in control['before']['alternatives']}
    now={a['project_id']:a for a in actual['alternatives']}
    no_update={a['project_id']:a for a in counterfactual['alternatives']}
    assert old.keys()==now.keys()==no_update.keys()
    assert math.isclose(now[pid]['score'],1.5)
    assert math.isclose(no_update[pid]['score'],old[pid]['score'])
    output=dict(schema='ala2-executive-native-fresh-process-v1',
        resolution_id=control['resolution']['resolution_id'],project_id=pid,goal=projects[pid]['goal'],
        question_scope='recurrence of score-reader review uncertainty; no explanation of reading errors',
        source_checkpoint_sequence=cutoff,same_opportunity_set=True,alternatives=len(now),
        before_score=old[pid]['score'],actual_after_reload_score=now[pid]['score'],scoped_ablated_score=no_update[pid]['score'],
        actual_selection=actual,ablation=counterfactual,physical_actions=0,independent_new_experiment=False,
        interpretation='authentic retained investigation changed actual later evaluation; controlled replay is not an independent trial')
    (R/'e1-fresh-process.json').write_text(json.dumps(output,indent=2,sort_keys=True)+'\n')
    print({k:v for k,v in output.items() if k not in ('actual_selection','ablation')})
finally:j.close()
