from pathlib import Path
import sys,faulthandler,json
sys.path.insert(0,'/home/five/charlie-ala2-recovery-20261019')
from memory.evidence import EvidenceJournal
from memory.evidence import digest
from memory.learning_projects import LearningExecutive
from memory.evaluator import MemoryEvaluator
from learning.lifecycle import DevelopmentLifecycle, run
from learning.resources import DevelopmentResources
from learning.episode_identity import verified_tracks
from learning.datasets import sha
from experiments.ppal.reflect_robotron import expose_score_review_contexts
BASE=Path('/home/five/ala2-recovery-20261019');R=BASE/'checkpoint-evaluation';state=R/'state'
faulthandler.dump_traceback_later(60,repeat=True)
text=(BASE/'run_recovery.py').read_text();start=text.index('class ObservedLifecycle');end=text.index('\nroots=',start)
exec(compile(text[start:end],str(BASE/'run_recovery.py'),'exec'),globals())
text=(BASE/'frozen_recovery.py').read_text();start=text.index('class FrozenCorpusLifecycle');end=text.index('\nrun(state',start)
exec(compile(text[start:end],str(BASE/'frozen_recovery.py'),'exec'),globals())
class FixedInputsLifecycle(FrozenCorpusLifecycle):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        original=self.executive.reassessment_ready
        cache={}
        def reassess(project_id,journal,spec):
            # Pure-function memoization only inside this declared frozen corpus.
            # New history/spec invalidates it. No cached result is independent
            # evidence, a notebook conclusion, or physical qualification.
            project=self.executive.projects()[project_id]
            key=digest(dict(project_id=project_id,spec=spec,history=project['experiment_history'],
                method=project['method'],bookmark=project.get('developmental_bookmark')))
            if key not in cache:cache[key]=original(project_id,journal,spec)
            return cache[key]
        self.executive.reassessment_ready=reassess
    def acquire(self):
        if getattr(self,'frozen_inputs_verified',False):return False
        result=super().acquire();self.frozen_inputs_verified=True;return result
run(state,[],budget_seconds=30.,interval=.05,turns=20,
    resources=DevelopmentResources(cpu_cores=1,memory_mb=2048),wall_seconds=1200.,
    lifecycle_factory=FixedInputsLifecycle)
