"""Native disarmed recovery through existing interfaces, on verified copies."""
from pathlib import Path
import json, shutil, sys
sys.path.insert(0,'/home/five/charlie-ala2-recovery-20261019')
from memory.evidence import EvidenceJournal, digest
from memory.learning_projects import LearningExecutive
from learning.retrospective import merge_history
from learning.lifecycle import DevelopmentLifecycle, run
from learning.resources import DevelopmentResources
from experiments.ppal.inspect_robotron_score import import_reviews
from experiments.ppal.score_feedback import reviewed_labels

R=Path('/home/five/ala2-recovery-20261019');state=R/'runtime-state'
assert (R/'runtime-copy.json').exists() and (R/'preservation.json').exists()
if '--resume' not in sys.argv:
    staging=R/'overnight-operational-history';staging.mkdir()
    for name in ('learning-evidence.sqlite3','meditations','pixels','preserved-findings'):
        source=R/'preserved/overnight'/name
        if source.is_dir():shutil.copytree(source,staging/name)
        elif source.is_file():shutil.copy2(source,staging/name)
    receipt=merge_history(staging,state)
    (R/'overnight-reconciliation.json').write_text(json.dumps(receipt,indent=2)+'\n')
    j=EvidenceJournal(state/'learning-evidence.sqlite3')
    try:
        receipt=import_reviews(j,R/'preserved/scores/learning-evidence.sqlite3')
        rows,excluded=reviewed_labels(j,partition='diagnostic')
        (R/'score-reconciliation.json').write_text(json.dumps(dict(receipt=receipt,
            eligible_diagnostic_labels=[dict(proposal_id=r['proposal_id'],label=r['label'],annotation_ids=r['annotation_ids']) for r in rows],
            excluded=excluded,held_out_training_labels=reviewed_labels(j,partition='training')[0]),indent=2,default=str)+'\n')
    finally:j.close()

class ObservedLifecycle(DevelopmentLifecycle):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.last_selection=None
        original_select=self.executive.select
        def select(**environment):
            result=original_select(**environment)
            if not environment.get('inspect'):
                self.last_selection=(environment,result)
            return result
        self.executive.select=select
        original_result=self.executive.record_result
        def record_result(*args,**kwargs):
            # Freeze the exact original opportunity set before delivering feedback.
            environment,selection=self.last_selection
            before=self.executive.select(**dict(environment,inspect=True))
            result=original_result(*args,**kwargs)
            # Fresh journal/Executive instance loads actual retained state. This
            # is a logged real selection through the ordinary chooser, with the
            # same capability/resource alternatives and no new Reflection pass.
            fresh=EvidenceJournal(self.journal.path)
            try:
                executive=LearningExecutive(fresh,self.gateway)
                after=executive.select(**environment)
            finally:fresh.close()
            report=dict(project_id=args[0],resolution=args[2],
                environment={k:sorted(v) if isinstance(v,set) else v for k,v in environment.items()},
                before=before,actual_after_reload=after,
                original_selection=selection,controller_writes=0,
                interpretation='actual later diagnostic valuation; claim validity and opportunity equality require review')
            with (R/'executive-controls.jsonl').open('a') as f:f.write(json.dumps(report,sort_keys=True)+'\n')
            return result
        self.executive.record_result=record_result

roots=[Path(g['paths'][0]) for g in json.loads((R/'unlinked.json').read_text())]
if '--resume' in sys.argv: roots=[p for p in roots if (p/'report.json').is_file()]
run(state,roots,budget_seconds=10.,interval=.05,turns=18,
    resources=DevelopmentResources(cpu_cores=1,memory_mb=2048),wall_seconds=1200.,
    lifecycle_factory=ObservedLifecycle)
