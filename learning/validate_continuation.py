"""Reproduce evidence-generated refinement in an isolated offline workspace.

No supplied hypothesis, architecture, labels, camera, START or deployment grant.
The input is an existing journal containing evaluated models and diagnostics.
"""
import argparse
import shutil
from pathlib import Path
from memory.evidence import EvidenceJournal
from memory.gateway import MemoryGateway
from memory.evaluator import MemoryEvaluator
from memory.store import JsonlStore
from memory.learning_projects import LearningExecutive
from .datasets import ExperienceDataset,sha
from .cycle import investigate,gameplay_active
from .foundry import atomic_json


def validate(source,output,*,budget_seconds=60.,pixels=None):
    if gameplay_active():raise RuntimeError('offline validation unavailable during gameplay')
    source=Path(source).resolve();output=Path(output).resolve()
    if output.exists():raise ValueError('choose a new isolated output directory; source evidence is never overwritten')
    output.mkdir(parents=True)
    original=EvidenceJournal(source/'learning-evidence.sqlite3')
    # SQLite backup captures a consistent committed source without WAL assumptions.
    journal=EvidenceJournal(output/'learning-evidence.sqlite3')
    original.conn.backup(journal.conn);journal.verify()
    preserved={r.id:r.document for r in original.records()};original.close()
    gateway=MemoryGateway(store=JsonlStore(output/'selected.jsonl'),evaluator=MemoryEvaluator(output/'evaluator.sqlite3'))
    dataset=ExperienceDataset(journal,output/'pixels')
    try:
        for row in dataset.examples():
            pixel=(Path(pixels) if pixels else source/'pixels')/(row['pixel_sha256']+'.png')
            if sha(pixel)!=row['pixel_sha256']:raise ValueError('source artifact changed')
            shutil.copy2(pixel,dataset.artifacts/pixel.name)
        dataset.locate_artifacts(dataset.artifacts)
        report=investigate(dataset,gateway,budget_seconds=budget_seconds,max_jobs=2,
            executive=LearningExecutive(journal,gateway),refinement_only=True)
        journal.verify()
        if not all(journal.get(i).document==doc for i,doc in preserved.items()):raise ValueError('historical evidence changed')
        summary=dict(source=str(source),source_journal_sha256=sha(source/'learning-evidence.sqlite3'),
            original_records_preserved=len(preserved),new_physical_experiments=0,
            elapsed=report['elapsed'],experiments=[dict(plan=r['plan'],result=r['result']) for r in report['results']],
            final_test_reopened=False,physical_score_improvement='not tested',
            interpretation='validation refinement on correlated archive evidence; not independent capability certification')
        atomic_json(output/'continuation-validation.json',summary)
        return summary
    finally:journal.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--budget-seconds',type=float,default=60.);p.add_argument('--pixels',type=Path,help='verified original content-hashed pixels if stored separately');a=p.parse_args()
    result=validate(a.source,a.output,budget_seconds=a.budget_seconds,pixels=a.pixels)
    print({k:result[k] for k in ('original_records_preserved','elapsed','new_physical_experiments','physical_score_improvement')})


if __name__=='__main__':main()
