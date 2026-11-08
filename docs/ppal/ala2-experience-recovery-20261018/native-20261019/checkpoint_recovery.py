"""Continue a quiesced, genuine acquisition checkpoint through the Executive.

All later bulk partial-session imports remain in runtime-state and its full
snapshot. This evaluation branch retains the contiguous 4,038-record checkpoint
after all nine eligible report ingestions and before bulk partial-session copy.
No original/overnight state or generated learning result is discarded.
"""
from pathlib import Path
import sqlite3, shutil, json, sys, hashlib
sys.path.insert(0,'/home/five/charlie-ala2-recovery-20261019')
from memory.evidence import EvidenceJournal, EvidenceRecord, digest
from memory.learning_projects import LearningExecutive
from memory.evaluator import MemoryEvaluator
from learning.lifecycle import DevelopmentLifecycle, run
from learning.resources import DevelopmentResources
from learning.episode_identity import verified_tracks
from learning.datasets import sha
from experiments.ppal.reflect_robotron import expose_score_review_contexts

BASE=Path('/home/five/ala2-recovery-20261019');R=BASE/'checkpoint-evaluation';R.mkdir()
source=BASE/'runtime-state';state=R/'state';state.mkdir();cutoff=4038
srcpath=source/'learning-evidence.sqlite3'
assert not any(Path(str(srcpath)+s).exists() for s in ('-wal','-shm','-journal'))
source_sha=sha(srcpath)
src=sqlite3.connect(srcpath.as_uri()+'?mode=ro&immutable=1',uri=True)
rows=[EvidenceRecord(*r) for r in src.execute('SELECT sequence,id,document,committed_at FROM records WHERE sequence<=? ORDER BY sequence',(cutoff,))];src.close()
class AcquiredPrefix:
    def records(self):return rows
    def verify(self):
        seen=set()
        for r in rows:
            data=r.data
            if digest(data)!=r.id or any(i not in seen for i in data['sources']):
                raise ValueError('invalid checkpoint content or causal order')
            seen.add(r.id)
prefix=AcquiredPrefix();prefix.verify()
target=EvidenceJournal(state/'learning-evidence.sqlite3');target.merge_from(prefix);target.close()
assert sha(srcpath)==source_sha
for name in ('evaluator.sqlite3','memory.jsonl','robotron-questions.jsonl','image-locations.json','imported-score-images','meditations','pixels','recovered-history','preserved-findings'):
    p=source/name
    if p.is_dir():shutil.copytree(p,state/name)
    elif p.exists():shutil.copy2(p,state/name)
(R/'snapshot.json').write_text(json.dumps(dict(source=str(srcpath),source_sha256=source_sha,
    checkpoint_sequence=cutoff,records=len(rows),original_record_ids=[r.id for r in rows],
    retained_later_bulk_history=str(source),new_independent_experience=False,
    physical_authorization=False),indent=2)+'\n')
del rows

text=(BASE/'run_recovery.py').read_text();start=text.index('class ObservedLifecycle');end=text.index('\nroots=',start)
exec(compile(text[start:end],str(BASE/'run_recovery.py'),'exec'),globals())
text=(BASE/'frozen_recovery.py').read_text();start=text.index('class FrozenCorpusLifecycle');end=text.index('\nrun(state',start)
exec(compile(text[start:end],str(BASE/'frozen_recovery.py'),'exec'),globals())
run(state,[],budget_seconds=10.,interval=.05,turns=18,
    resources=DevelopmentResources(cpu_cores=1,memory_mb=2048),wall_seconds=900.,
    lifecycle_factory=FrozenCorpusLifecycle)
