"""Recover and investigate preserved Robotron experience without hardware.

Uses the existing journal, Reflection, Executive, Evaluator, chooser and
meditation candidates. Imported interpretations remain unverified diagnostics.
"""
import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path
import shutil

from memory.evidence import EvidenceJournal, digest
from memory.evaluator import MemoryEvaluator
from memory.gateway import MemoryGateway
from memory.store import JsonlStore
from .datasets import ExperienceDataset, SCOPE, sha
from .foundry import atomic_json

VERSION = 'ala-2-retrospective-recovery-v1'


def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p)
            for p in sorted(Path(root).rglob('*')) if p.is_file()}


def recover_notebook(source, output):
    """Copy once, retaining every original byte and immutable content ID."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('recovery requires a separate destination')
    before = inventory(source)
    journal = EvidenceJournal(source/'learning-evidence.sqlite3', read_only=True)
    try:
        ids = [r.id for r in journal.records()]
    finally:
        journal.close()
    receipt = dict(source_digest=digest(before), journal_content_ids=ids)
    if output.exists():
        saved = output/'recovery-origin.json'
        if not saved.is_file() or json.loads(saved.read_text()) != receipt:
            raise ValueError('existing output is not this recovered notebook')
        return receipt
    # A partial copy is retained on error. Never replace an existing notebook.
    shutil.copytree(source, output)
    if inventory(output) != before or inventory(source) != before:
        raise ValueError('notebook changed during recovery')
    atomic_json(output/'recovery-origin.json', receipt)
    return receipt


def _rows(root, name):
    p = root/name
    rows, torn = [], []
    if p.exists():
        for line, value in enumerate(p.read_text().splitlines(), 1):
            if not value.strip():
                continue
            try:
                row = json.loads(value)
                if not isinstance(row, dict):
                    raise ValueError('object required')
                rows.append(row)
            except ValueError:
                torn.append(line)
    return rows, torn


def merge_history(source, output):
    """Preserve another notebook intact, then merge exact original record IDs."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('history source must be separate from learning output')
    if not (source/'learning-evidence.sqlite3').is_file():
        return dict(source=str(source), status='unavailable', reason='original journal unavailable; no empty history inferred')
    before = inventory(source)
    snapshot = output/'recovered-history'/digest(before)
    if not snapshot.exists():
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, snapshot)
    if inventory(snapshot) != before or inventory(source) != before:
        raise ValueError('history changed during preservation')
    original = EvidenceJournal(snapshot/'learning-evidence.sqlite3', read_only=True)
    target = EvidenceJournal(output/'learning-evidence.sqlite3')
    try:
        ids = [r.id for r in original.records()]
        added = target.merge_from(original)
        receipt = dict(source=str(source), snapshot=str(snapshot), inventory_digest=digest(before),
            original_ids=ids, history_import=True, new_physical_experience=False,
            semantic_memory_delivery='not inferred from journal import')
        target.append('event', dict(category='notebook_history_recovery', **receipt),
            episode=SCOPE, producer='existing-evidence-consolidation', version=VERSION)
        return dict(status='preserved', original_records=len(ids), added_records=len(added), **receipt)
    finally:
        original.close(); target.close()


def discover_episodes(roots):
    """Discover finalized archives only; ingestion validates/deduplicates copies."""
    return sorted({p.parent.resolve() for root in roots
                   for p in Path(root).rglob('report.json')})


def discover(root):
    """Report gaps to Reflection; never select an agenda or certify outcomes."""
    root = Path(root)
    report = json.loads((root/'report.json').read_text()) if (root/'report.json').exists() else {}
    agency, torn = _rows(root, 'agency.jsonl')
    identities = Counter('unknown' if r.get('self_track_id') is None else 'reported_self' for r in agency)
    executions = {digest(r['control_execution']): r['control_execution'] for r in agency if r.get('control_execution')}
    steps = report.get('steps', [])
    scores, score_torn = _rows(root, 'score.jsonl')
    questions = []
    def question(category, text, measured):
        questions.append(dict(category=category, question=text, measured=measured))
    if identities['unknown']:
        question('self_uncertainty', 'Which observations distinguish lost ownership from disappearance?', dict(identities))
    if agency:
        question('ownership_continuity', 'Which independent same-object observations qualify ownership across gaps?', {'samples':len(agency)})
    question('death_observability', 'Which independent life-boundary observations identify pre-death windows?', {'qualified_deaths':None})
    if executions:
        question('action_execution', 'Which same-identity response windows distinguish command transport from physical effects?', {'unique_transports':len(executions)})
    if steps:
        question('semantic_coverage', 'Do independently annotated roles support the reported rescue and threat opportunities?', {'decisions':len(steps)})
    if scores or 'score' in report:
        question('score_attribution', 'Which independent terminal captures can qualify a complete-game score?', {'reported_score':report.get('score')})
    return dict(identity_samples=dict(identities), questions=questions,
        reported_score=report.get('score'), score_class='historical subsystem report; complete game unqualified',
        complete_game_score=False, verified_deaths=None, unique_transports=len(executions),
        actions_status='recorded transport is not proof of physical effect',
        planning_decisions=len(steps), score_rows=len(scores),
        torn_lines={'agency.jsonl':torn, 'score.jsonl':score_torn},
        partial=not (root/'report.json').exists(), causal_performance_change='UNKNOWN')


def ingest(root, dataset):
    """Preserve saved findings and exact source manifests, with retry dedup."""
    from experiments.ppal.episode_evidence import import_episode
    from .meditation import consume
    root = Path(root).resolve()
    before = inventory(root)
    if not before:
        raise ValueError('empty archive')
    episode = 'episode:'+before['report.json'] if 'report.json' in before else 'partial-episode:'+digest(before)
    journal = dataset.journal
    existing = [r for r in journal.records() if r.data['payload'].get('category') == 'retrospective_ingestion'
                and r.data['payload'].get('source_episode') == episode]
    if existing:
        marker = existing[-1].data['payload']
        context = journal.get(marker['context_id']).data['payload']
        if marker.get('meditation_id'):
            saved = root.parent/(root.name+'-evidence')/'meditation.json'
            expected = journal.get(marker['meditation_id']).data['payload']['artifact_sha256']
            if not saved.is_file() or sha(saved) != expected:
                raise ValueError('preserved meditation artifact changed or missing')
        frozen = context.get('inventory')
        if frozen is not None and frozen != before:
            raise ValueError('preserved source artifacts changed')
        # Older notebooks locate the original episode manifest in a separate
        # journal. Relocation changes paths, never its capture hashes.
        if frozen is None:
            source_path = dataset.artifacts.parent/'episodes'/Path(context['source_journal']).name
            source = EvidenceJournal(source_path, read_only=True)
            try:
                manifests = [r.data['payload']['artifacts'] for r in source.records('episode')
                             if r.data['episode'] == episode]
                if not manifests or any(before.get(name) != ref['sha256']
                    for name, ref in manifests[0].items()):
                    raise ValueError('preserved source artifacts changed')
            finally:
                source.close()
        return dict(status='preserved', source_episode=episode, record_id=existing[-1].id,
                    relocated_inventory_digest=digest(before))
    source = EvidenceJournal(dataset.artifacts.parent/'episodes'/(digest(episode)+'.sqlite3'))
    try:
        imported = import_episode(root, source)
        context = discover(root)
        # Durable consolidated context is an interpretation, not independent truth.
        ref = journal.append('observation', dict(category='learning_context_reference',
            source_episode=episode, source_journal=str(source.path.resolve()),
            context=context, inventory=before, prior_use='diagnostic'), episode=SCOPE,
            producer='existing-evidence-consolidation', version=VERSION)
        saved = root.parent/(root.name+'-evidence')/'meditation.json'
        history = json.loads((Path(__file__).resolve().parents[1]/'docs/ppal/ala-1-demonstration.json').read_text())['snapshot_split']
        prior = history.get(episode, 'diagnostic')
        prior = 'consulted-test' if prior == 'test' else prior
        med = consume(dataset, saved, source_episode=episode, prior_use=prior) if saved.exists() else None
        if inventory(root) != before:
            raise ValueError('archive changed during ingestion')
        completed = journal.append('event', dict(category='retrospective_ingestion',
            source_episode=episode, physical_episode=imported, context_id=ref.id,
            meditation_id=med.id if med else None, inventory_digest=digest(before),
            preserved_bytes_unchanged=True, prior_use=prior), episode=SCOPE,
            sources=[ref.id]+([med.id] if med else []), producer='existing-evidence-consolidation', version=VERSION)
        return dict(status='imported', source_episode=episode, record_id=completed.id)
    finally:
        source.close()


def run(roots, output, *, budget_seconds=60., max_jobs=8, qualify_observations=False):
    from .cycle import gameplay_active, investigate
    if gameplay_active():
        raise RuntimeError('offline only: active gameplay')
    if not 1 <= max_jobs <= 8 or not 1 <= budget_seconds <= 3600:
        raise ValueError('bounded offline resources required')
    output = Path(output).resolve()
    roots = [Path(r).resolve() for r in roots]
    if any(output == r or output in r.parents or r in output.parents for r in roots):
        raise ValueError('output must be separate from preserved evidence')
    output.mkdir(parents=True, exist_ok=True)
    with (output/'retrospective.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (output/'offline.lock').open('a') as offline_lock:
            fcntl.flock(offline_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            journal = EvidenceJournal(output/'learning-evidence.sqlite3')
            evaluator = MemoryEvaluator(output/'evaluator.sqlite3')
            gateway = MemoryGateway(store=JsonlStore(output/'memory.jsonl'), evaluator=evaluator)
            try:
                dataset = ExperienceDataset(journal, output/'pixels')
                imports = [ingest(r, dataset) for r in roots]
                qualifications = []
                if qualify_observations:
                    from .archive_audit import audit, ingest as ingest_qualification
                    qualifications = [ingest_qualification(journal,audit(r.parent if r.name=='game-01' else r)) for r in roots]
                result = investigate(dataset, gateway, diagnostics_only=True, review_questions=True,
                    budget_seconds=budget_seconds, max_jobs=max_jobs)
                requests = []
                if qualifications:
                    from memory.learning_projects import LearningExecutive
                    executive = LearningExecutive(journal,gateway)
                    for identifier,project in executive.projects().items():
                        if (project['method'] not in ('meditation-motion','evidence-review')
                                or project['status'] not in ('paused','blocked') or not project['experiment_history']):
                            continue
                        outcome=project['experiment_history'][-1]
                        if outcome['result'] not in ('unresolved','contradicted'):
                            continue
                        plan=next(r.data['payload']['plan'] for r in journal.records('event')
                            if r.data['payload'].get('category')=='offline_experiment_plan'
                            and r.data['payload']['plan']['prediction_id']==outcome['prediction_id'])
                        if project['method']=='evidence-review' and plan.get('predicate')!='capture_horizon_supported':
                            continue
                        origins={journal.get(i).data['payload'].get('source_episode') for i in plan['source_evidence']}
                        matching=[r.id for r in qualifications if r.data['payload']['source_episode'] in origins]
                        if matching:
                            requests.append(executive.retain_evidence_request(identifier,journal,matching).id)
                    result['projects']=executive.projects()
                journal.verify()
                report = dict(schema=VERSION, ingestion=imports, new_investigations=result['results'],
                    projects=result['projects'], physical_authorization=False, physical_policy_activated=False,
                    acceptance='ALA-2 incomplete; verified complete-game improvement unproven',
                    journal_content_ids=[r.id for r in journal.records()],
                    contexts=[r.data['payload'] for r in journal.records('observation')
                              if r.data['payload'].get('category') == 'learning_context_reference'],
                    qualification_ids=[r.id for r in qualifications],evidence_request_ids=requests)
                target = output/'reports'/(digest(report)+'.json')
                target.parent.mkdir(exist_ok=True)
                if not target.exists():
                    atomic_json(target, report)
                return dict(report=str(target), new_investigations=len(result['results']),
                            records=len(journal.records()), physical_authorization=False)
            finally:
                journal.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recover-notebook', type=Path)
    parser.add_argument('--merge-history', type=Path, action='append', default=[])
    parser.add_argument('--episode-root', type=Path, action='append', default=[])
    parser.add_argument('--budget-seconds', type=float, default=60.)
    parser.add_argument('--max-jobs', type=int, default=8)
    parser.add_argument('--qualify-observations',action='store_true',
        help='audit preserved capture availability and retain Executive acquisition bookmarks; no hardware access')
    args = parser.parse_args()
    from .cycle import gameplay_active
    if gameplay_active():
        parser.error('offline only: active gameplay')
    if not 1 <= args.max_jobs <= 8 or not 1 <= args.budget_seconds <= 3600:
        parser.error('bounded offline resources required')
    if args.recover_notebook:
        recover_notebook(args.recover_notebook, args.output)
    # Same offline ownership as normal cycle execution; history merge itself
    # does not select or repeat investigations.
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output/'offline.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        histories = [merge_history(p, args.output) for p in args.merge_history]
    result = run(args.episode + discover_episodes(args.episode_root), args.output,
        budget_seconds=args.budget_seconds, max_jobs=args.max_jobs,
        qualify_observations=args.qualify_observations)
    print(json.dumps(dict(result, histories=histories)))


if __name__ == '__main__':
    main()
