"""Controlled native continuation of an acquired copied corpus, no new trials.

Snapshot the isolated acquisition output with SQLite backup. Do not reset or
reimport originals. Freeze acquisition so Executive controls cannot be confounded
by additional opportunities appearing between the before/outcome/after steps.
"""
from pathlib import Path
import sqlite3, shutil, json, sys, hashlib
sys.path.insert(0,'/home/five/charlie-ala2-recovery-20261019')
from memory.evidence import EvidenceJournal
from memory.learning_projects import LearningExecutive
from memory.evaluator import MemoryEvaluator
from learning.lifecycle import DevelopmentLifecycle, run
from learning.resources import DevelopmentResources
from learning.episode_identity import verified_tracks
from learning.datasets import sha
from experiments.ppal.reflect_robotron import expose_score_review_contexts

BASE=Path('/home/five/ala2-recovery-20261019');R=BASE/'frozen-evaluation';R.mkdir()
source=BASE/'runtime-state';state=R/'state';state.mkdir()
for name in ('learning-evidence.sqlite3','evaluator.sqlite3'):
    src=sqlite3.connect((source/name).as_uri()+'?mode=ro',uri=True)
    dst=sqlite3.connect(state/name);src.backup(dst);assert dst.execute('PRAGMA quick_check').fetchone()[0]=='ok'
    dst.close();src.close()
for name in ('memory.jsonl','robotron-questions.jsonl','image-locations.json','imported-score-images','meditations','pixels','recovered-history','preserved-findings'):
    p=source/name
    if p.is_dir():shutil.copytree(p,state/name)
    elif p.exists():shutil.copy2(p,state/name)
conn=sqlite3.connect((state/'learning-evidence.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
identifiers=[r[0] for r in conn.execute('SELECT id FROM records ORDER BY sequence')];conn.close()
(R/'snapshot.json').write_text(json.dumps(dict(source=str(source),snapshot_records=len(identifiers),
    original_record_ids=identifiers,physical_authorization=False,new_independent_experience=False,
    reason='Controlled continuation of already acquired corpus; no new acquisition opportunities'),indent=2)+'\n')

# Reuse exactly the observation hooks from the ordinary-lifecycle harness.
text=(BASE/'run_recovery.py').read_text();start=text.index('class ObservedLifecycle');end=text.index('\nroots=',start)
exec(compile(text[start:end],str(BASE/'run_recovery.py'),'exec'),globals())
class FrozenCorpusLifecycle(ObservedLifecycle):
    def acquire(self):
        # Existing identity/track validator, existing score Reflection and
        # immutable result hashes. No synthetic observations or replacement
        # tracks, no independent-evidence qualification inferred from a copy.
        self.available_tracks=verified_tracks(self.journal)
        self.acquisition_roots=[]
        for record in self.journal.category_records('observation','normal_meditation_result'):
            p=record.data['payload'];candidates=[Path(p['result_path'])]
            candidates+=list((self.output/'meditations'/p['context_id']).glob('**/result.json'))
            candidates+=list((self.output/'recovered-history').glob('*/meditations/'+p['context_id']+'/**/result.json'))
            if not any(path.is_file() and sha(path)==p['result_sha256'] for path in candidates):
                raise ValueError('frozen corpus meditation artifact unavailable or changed')
        MemoryEvaluator.reconcile_score_reviews(self.journal)
        expose_score_review_contexts(self.dataset)
        return False

run(state,[],budget_seconds=10.,interval=.05,turns=18,
    resources=DevelopmentResources(cpu_cores=1,memory_mb=2048),wall_seconds=1200.,
    lifecycle_factory=FrozenCorpusLifecycle)
