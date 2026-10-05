"""Preserved meditation -> executable, unarmed planning candidate.

Retrospective tracking errors motivate an investigation, never certify a motion
model. The finite candidate vocabulary changes temporal estimation, not strategy.
No camera, controller, physical authority or annotation generator lives here.
"""
import json
import math
from pathlib import Path
import time

from memory.evidence import canonical, digest
from memory.former import Experience
from .datasets import SCOPE, sha

VERSION = 'meditation-motion-v1'


def qualify_corpus(dataset, path):
    """Bind external trajectory measurements to exact saved capture bytes.

    This validates provenance and separation, not the truth of the external
    annotation. Independent annotators must establish identities from frames.
    """
    p = Path(path)
    corpus = json.loads(p.read_text())
    if corpus.get('source_kind') not in ('external_annotation','independent_measurement'):
        raise ValueError('model/replay labels cannot qualify motion')
    reference = corpus.get('qualification_artifact',{})
    if not reference.get('path') or sha(reference['path'])!=reference.get('sha256'):
        raise ValueError('hash-bound independent qualification artifact required')
    episodes = corpus.get('episodes',[])
    if not 4<=len(episodes)<=128:
        raise ValueError('validation and at least three independent final episodes required')
    known = json.loads((Path(__file__).resolve().parents[1]/'docs/ppal/ala-1-demonstration.json').read_text())
    # Known published use must survive a new root, host or copied notebook.
    used = set(known['snapshot_split'])
    from .episode_identity import qualified_reference
    ids=set(); captures={}; final=0; validation=0; identities=[]
    for episode in episodes:
        identity=episode.get('source_episode')
        partition=episode.get('partition')
        report=episode.get('source_report',{})
        receipt=qualified_reference(dataset.journal,identity,report,capture_root=episode.get('source_capture_root'))
        identities.append(receipt)
        group=receipt['experience_id']
        if not identity or group in ids or partition not in ('validation','test'):
            raise ValueError('unique physical episode and frozen partition required')
        ids.add(group)
        if partition=='test':
            final+=1
            if identity in used or 'episode:'+report['sha256'] in used or episode.get('prior_use')!='unconsulted':
                raise ValueError('fresh final episodes required; published/declared prior use blocks reuse')
        else: validation+=1
        frames=episode.get('frames',[])
        if not 3<=len(frames)<=4096: raise ValueError('bounded qualified trajectory required')
        previous=None
        for frame in frames:
            at=frame.get('timestamp')
            if not isinstance(at,(int,float)) or not math.isfinite(at) or (previous is not None and at<=previous):
                raise ValueError('increasing finite capture timestamps required')
            previous=at
            artifact=frame.get('artifact',{})
            if not artifact.get('path') or sha(artifact['path'])!=artifact.get('sha256'):
                raise ValueError('exact capture artifact required')
            h=artifact['sha256']
            if h in captures and captures[h]!=identity:
                raise ValueError('duplicate captures connect purported independent episodes')
            captures[h]=identity
            if frame.get('identity_status')!='independently_verified':
                raise ValueError('independently verified identities required')
            world_from_frame(frame)  # Validate coordinates and role identities before committing.
    if final<3 or validation<1: raise ValueError('validation and three final episodes required')
    return dataset.journal.append('observation',dict(category='independent_motion_corpus',
        corpus=corpus,identity_references=identities,artifact_sha256=sha(p)),episode=SCOPE,
        producer='external-motion-qualification',version=VERSION)


def world_from_frame(frame):
    from experiments.ppal.models import Position,Object,WorldState
    def position(values):
        if len(values)!=2 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=100 for v in values):
            raise ValueError('finite board coordinates required')
        return Position(*values)
    seen={'player'}
    def objects(role):
        result=[]
        for item in frame.get(role,[]):
            if not item.get('id') or item['id'] in seen: raise ValueError('unique persistent physical IDs required')
            seen.add(item['id']);result.append(Object(item['id'],position(item['position'])))
        return tuple(result)
    return WorldState(tick=frame.get('tick',0),player=position(frame['player']),
        targets=objects('targets'),threats=objects('threats'),alive=True,unresolved=())


def motion_error(spec, episodes):
    """Causal projection: observe only past/current frames, score the next frame."""
    from math import hypot
    errors=[];baseline=[];groups=[];qualified=0
    for episode in episodes:
        adapter=PlanningCandidate(spec); measurements=[]; bases=[]
        frames=episode['frames']
        for i,frame in enumerate(frames[:-1]):
            world=world_from_frame(frame)
            prediction=adapter.project(world,frame['timestamp'])
            future=frames[i+1]
            if i<1 or abs(future['timestamp']-frame['timestamp']-.15)>.025:
                continue
            actual=world_from_frame(future)
            now={'player':world.player,**{o.id:o.position for o in (*world.targets,*world.threats)}}
            pred={'player':prediction.player,**{o.id:o.position for o in (*prediction.targets,*prediction.threats)}}
            later={'player':actual.player,**{o.id:o.position for o in (*actual.targets,*actual.threats)}}
            for identity in now.keys() & later.keys():
                target=later[identity]
                measurements.append(hypot(pred[identity].x-target.x,pred[identity].y-target.y))
                bases.append(hypot(now[identity].x-target.x,now[identity].y-target.y))
        if not measurements: raise ValueError('no qualified time-compatible motion pairs in an episode')
        errors.append(sum(measurements)/len(measurements));baseline.append(sum(bases)/len(bases))
        qualified+=len(measurements);groups.append(episode['source_episode'])
    return dict(candidate=sum(errors)/len(errors),baseline=sum(baseline)/len(baseline),
        independence_groups=groups,per_episode=list(zip(errors,baseline)),qualified_observations=qualified)


def consume(dataset, path, *, source_episode, prior_use):
    """Import an exact preserved finding, with explicit historical evidence use."""
    if prior_use not in ('train', 'validation', 'consulted-test', 'diagnostic'):
        raise ValueError('explicit historical use required')
    p = Path(path)
    finding = json.loads(p.read_text())
    quality = finding['quality']
    for kind in ('adjacent', 'gaps'):
        value = quality[kind]['mean_error']
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('finite preserved prediction errors required')
    return dataset.journal.append('observation', dict(category='preserved_meditation',
        artifact_sha256=sha(p), source_episode=source_episode, prior_use=prior_use,
        finding=finding, qualification='retrospective unverified track reconstruction'),
        episode=SCOPE, producer='existing-evidence-consolidation', version=VERSION)


def reflect(dataset, gateway, registry):
    """Charlie proposes temporal estimation work only when his finding supports it."""
    from .episode_identity import eligible
    output = []
    corpora=[r for r in dataset.journal.records('observation') if r.data['payload'].get('category')=='independent_motion_corpus' and eligible(dataset.journal,r.data['payload'])]
    corpus_id=corpora[-1].id if corpora else None
    for record in dataset.journal.records('observation'):
        p = record.data['payload']
        if p.get('category') != 'preserved_meditation' or not eligible(dataset.journal,p):
            continue
        q = p['finding']['quality']
        if q['gaps']['mean_error'] <= q['adjacent']['mean_error']:
            continue
        alternatives = [dict(explanation='Temporal estimates may fail across gaps'),
                        dict(explanation='Retrospective associations may be wrong')]
        spec = dict(method='meditation-motion', scope={'meditation_id':record.id,'corpus_id':corpus_id},
            expected='An independently qualified temporal candidate improves held-out motion error',
            predicate='independent_motion_improvement', dataset_id=corpus_id or record.id,
            independence_unit=p['source_episode'], evidence_groups=[p['source_episode']],
            source_evidence=[record.id], alternatives=alternatives, rank=[1],
            question='Can temporal estimation improve without promoting uncertain track links?')
        hypothesis = dataset.journal.append('event', dict(category='perceptual_experiment_proposal',proposal=spec),
            episode=SCOPE,sources=[record.id],producer='Reflection',version=VERSION)
        gateway.remember(Experience(kind='observation',summary='Perceptual experiment hypothesis: '+canonical(spec),
            source='ppal:perceptual-reflection',subject=spec['method'],confidence=.5,significant=True,
            novelty=True,tags=('hypothesis','offline','tentative'),evidence=hypothesis.id))
        proposal = dict(originator='Reflection',method=spec['method'],scope=spec['scope'],expected=spec['expected'],
            goal=spec['question'],motivation='Preserved meditation reports higher prediction error across gaps',
            open_questions=[a['explanation'] for a in alternatives],requires=['offline-slot','meditation-evidence'],
            dependencies=[],established_objective='official_game_score',objective_contribution=.5,
            learning_value=.8,uncertainty=1.,cost=registry.get(spec['method']).cost,risk=.1,
            priority_provenance='declared bounded temporal investigation; no score utility inferred',
            tactical_hypothesis_evidence=[hypothesis.id],conditions=[],revision=VERSION)
        event = dataset.journal.append('event',dict(category='learning_project_proposal',proposal=proposal),
            episode=SCOPE,sources=[hypothesis.id],producer='Reflection',version=VERSION)
        output.append(dict(proposal=proposal,evidence_id=event.id,hypothesis_id=hypothesis.id))
    return output


class PlanningCandidate:
    """Executable temporal adapter around the existing Forebrain/Hindbrain.

    Offline execution only. Identity, acquisition and controller guards belong
    to PPAL; this adapter neither establishes identities nor sends an action.
    """
    def __init__(self, spec):
        from experiments.ppal.shadow_predictor import ShadowPredictor
        if spec.get('adapter') != VERSION or spec.get('velocity_alpha') not in (.35,.65,.85):
            raise ValueError('unsupported frozen temporal candidate')
        if spec.get('horizon_seconds') != .15 or spec.get('max_speed') != 100.:
            raise ValueError('existing diagnostic timing and speed bounds required')
        self.spec = spec
        self.predictor = ShadowPredictor(velocity_alpha=spec['velocity_alpha'],
            horizon_seconds=spec['horizon_seconds'],max_speed=spec['max_speed'])

    def project(self, world, timestamp):
        self.predictor.observe(world,timestamp)
        return self.predictor.project(world)

    def decide(self, world, timestamp, forebrain, hindbrain):
        projected = self.project(world,timestamp)
        return hindbrain.decide(projected,forebrain.update(projected))


def execute(plan, dataset, output=None, **unused):
    """Generate executable artifacts, then fail closed on absent ground truth.

    Independent motion evaluation is deliberately not approximated using the
    meditation's own reconstructed tracks. A new qualified corpus is necessary.
    """
    from .cycle import gameplay_active
    from .clock import domain
    if gameplay_active():
        raise RuntimeError('offline candidate unavailable during gameplay')
    journal = dataset.journal
    committed = [r.data['payload']['plan'] for r in journal.records('event')
        if r.data['payload'].get('category')=='offline_experiment_plan'
        and r.data['payload']['plan']['prediction_id']==plan['prediction_id']]
    if committed != [plan]:
        raise ValueError('execution must match the exact committed chooser plan')
    previous = journal.resolution_for(plan['prediction_id'])
    if previous:
        evaluation = [r for r in journal.records('observation')
            if r.data['payload'].get('category')=='meditation_candidate_evaluation'
            and r.data['payload'].get('prediction_id')==plan['prediction_id']][-1]
        return dict(status='already_resolved',resolution=previous.data['payload'],resolution_id=previous.id,
                    evaluation_id=evaluation.id,**evaluation.data['payload']['result'])
    finding = journal.get(plan['source_evidence'][0]).data['payload']
    if finding.get('category')!='preserved_meditation':
        raise ValueError('preserved meditation required')
    if plan['clock_domain']!=domain():
        result=dict(result='unresolved',reason='Host clock domain changed; prediction continuity UNKNOWN',
            metrics={'clock_continuity':'UNKNOWN'},operational_proposal=None,baseline_preserved=True)
        evaluation=journal.append('observation',dict(category='meditation_candidate_evaluation',
            prediction_id=plan['prediction_id'],ee_episode=SCOPE,result=result),episode=plan['episode'],
            sources=[plan['prediction_id']],producer='ModelFoundry',version=VERSION)
        resolution=journal.resolve(plan['prediction_id'],sources=[],result='unresolved',reason=result['reason'])
        return dict(status='resolved',evaluation_id=evaluation.id,resolution_id=resolution.id,**result)
    # A crash reuses the exact already committed outcome and artifacts.
    prior = [r for r in journal.records('observation')
        if r.data['payload'].get('category')=='meditation_candidate_evaluation'
        and r.data['payload'].get('prediction_id')==plan['prediction_id']]
    if len(prior)>1: raise ValueError('conflicting candidate outcomes')
    if prior:
        evaluation = prior[0]
    else:
        root = Path(output or dataset.artifacts.parent/'models')/plan['prediction_id']
        root.mkdir(parents=True,exist_ok=True)
        candidates = []
        for alpha in (.35,.65,.85):
            spec = dict(adapter=VERSION,velocity_alpha=alpha,horizon_seconds=.15,max_speed=100.)
            identifier = digest(dict(spec=spec,origin=plan['source_evidence']))
            artifact = root/(identifier+'.json')
            content = canonical(spec)+'\n'
            if artifact.exists() and artifact.read_text()!=content:
                raise ValueError('candidate artifact changed')
            if not artifact.exists():
                with artifact.open('x') as stream: stream.write(content)
            candidates.append(dict(identifier=identifier,checkpoint=str(artifact.resolve()),
                checkpoint_sha256=sha(artifact),spec=spec,originator='Reflection',
                source_evidence=plan['source_evidence']))
        reasons = ['No independently verified player/target/threat trajectories supplied',
                   'Meditation associations and error summaries are not independent ground truth',
                   'No fresh sealed final motion evaluation or operational shadow qualification']
        if finding['prior_use']!='diagnostic':
            reasons.append('Source episode already used as '+finding['prior_use']+'; not fresh final evidence')
        if plan['clock_domain']!=domain(): reasons.append('Host clock continuity UNKNOWN')
        result = dict(result='unresolved',reason='; '.join(reasons),metrics=dict(
            improved=False,fresh_final_evidence=False,qualified_observations=0,
            gates=reasons,score_improvement='UNKNOWN'),candidates=candidates,
            operational_proposal=None,baseline_preserved=True)
        corpora = ([journal.get(plan['condition']['corpus_id'])] if plan['condition'].get('corpus_id') else [])
        if len(corpora)==1 and plan['clock_domain']==domain():
            corpus_record=corpora[0]
            corpus=corpus_record.data['payload']['corpus']
            consulted={e for r in journal.records('observation')
                if r.data['payload'].get('category')=='motion_final_consultation'
                for e in r.data['payload']['episodes']}
            finals=[e for e in corpus['episodes'] if e['partition']=='test']
            if consulted & {e['source_episode'] for e in finals}:
                result['reason']='Final motion episodes already consulted; no new final evaluation or deployment'
            else:
                # Check relocated artifacts against their frozen hashes before any evaluation.
                refs=[corpus['qualification_artifact']]+[e['source_report'] for e in corpus['episodes']]+[
                    f['artifact'] for e in corpus['episodes'] for f in e['frames']]
                if any(sha(ref['path'])!=ref['sha256'] for ref in refs):
                    raise ValueError('qualified corpus artifact changed')
                validation=[e for e in corpus['episodes'] if e['partition']=='validation']
                scores=[motion_error(c['spec'],validation) for c in candidates]
                selected=min(zip(candidates,scores),key=lambda pair:(pair[1]['candidate'],pair[0]['identifier']))[0]
                selected=dict(selected,dataset_digest=corpus_record.id)
                # Commit consumption BEFORE opening/scoring final measurements. Interrupted
                # final evaluation stays spent; never silently rerun after a crash.
                journal.append('observation',dict(category='motion_final_consultation',
                    episodes=[e['source_episode'] for e in finals],candidate_id=selected['identifier'],
                    prediction_id=plan['prediction_id']),episode=plan['episode'],
                    sources=[plan['prediction_id']],producer='ModelFoundry',version=VERSION)
                metrics=motion_error(selected['spec'],finals)
                metrics.update(fresh_final_evidence=True,improved=all(a+.05<b for a,b in metrics['per_episode']),
                    score_improvement='UNKNOWN',validation_scores=scores,selected_by='validation only',
                    provenance_kind=corpus.get('provenance_kind','unclassified'))
                if time.monotonic()>journal.get(plan['prediction_id']).data['payload']['deadline']:
                    metrics.update(improved=False,prediction_horizon='expired')
                measured=journal.append('observation',dict(category='offline_model_evaluation',
                    candidate=selected,metrics=metrics),episode=plan['episode'],
                    sources=[plan['prediction_id']],producer='ModelFoundry',version=VERSION)
                proposal=journal.append('event',dict(category='model_deployment_proposal',
                    eligible=metrics['improved'],target='offline-shadow',candidate_id=selected['identifier'],
                    prediction_id=plan['prediction_id'],evaluation_id=measured.id),episode=plan['episode'],sources=[measured.id],
                    producer='Reflection',version=VERSION)
                result.update(result='supported' if metrics['improved'] else 'contradicted',
                    reason='Independent held-out motion comparison; physical score utility remains UNKNOWN',
                    metrics=metrics,deployment_proposal=proposal.id,selected_candidate=selected)
        evaluation = journal.append('observation',dict(category='meditation_candidate_evaluation',
            prediction_id=plan['prediction_id'],ee_episode=SCOPE,result=result),episode=plan['episode'],
            at=time.monotonic(),sources=[plan['prediction_id']],producer='ModelFoundry',version=VERSION)
    result = evaluation.data['payload']['result']
    resolution = journal.resolve(plan['prediction_id'],sources=[evaluation.id],
        result=result['result'],reason=result['reason'])
    return dict(status='resolved',resolution_id=resolution.id,evaluation_id=evaluation.id,**result)


def shadow(journal, proposal_id):
    """Unarmed candidate-specific executable compatibility check, not utility."""
    from .cycle import gameplay_active
    from experiments.ppal.forebrain import Forebrain
    from experiments.ppal.hindbrain import Hindbrain
    if gameplay_active(): raise RuntimeError('offline shadow unavailable during gameplay')
    proposal=journal.get(proposal_id)
    p=proposal.data['payload']
    if p.get('category')!='model_deployment_proposal' or not p.get('eligible') or p['target']!='offline-shadow':
        raise ValueError('eligible offline proposal required')
    evaluation=journal.get(p['evaluation_id']).data['payload']
    candidate=evaluation['candidate']
    if sha(candidate['checkpoint'])!=candidate['checkpoint_sha256']:
        raise ValueError('candidate artifact changed')
    corpus=journal.get(candidate['dataset_digest']).data['payload']['corpus']
    steps=0
    for episode in corpus['episodes']:
        if episode['partition']!='validation': continue  # Do not reopen final frames.
        adapter=PlanningCandidate(candidate['spec']);forebrain=Forebrain();hindbrain=Hindbrain()
        for frame in episode['frames']:
            world=world_from_frame(frame)
            intent,action=adapter.decide(world,frame['timestamp'],forebrain,hindbrain)
            if not action.move or not action.fire or not intent.kind:
                raise ValueError('existing chooser produced an invalid action')
            steps+=1
    if not steps: raise ValueError('no shadow observations')
    return journal.append('observation',dict(category='motion_operational_shadow',passed=True,
        proposal_id=proposal_id,candidate_id=candidate['identifier'],
        checkpoint_sha256=candidate['checkpoint_sha256'],steps=steps,controller_writes=0,
        limitation='executable compatibility only; no physical readiness or score utility'),
        episode=proposal.data['episode'],sources=[proposal_id],
        producer='controlled-motion-adapter',version=VERSION)


def main():
    """Reproduce archive admission outcomes in a NEW isolated offline notebook."""
    import argparse
    from memory.evidence import EvidenceJournal
    from memory.evaluator import MemoryEvaluator
    from memory.gateway import MemoryGateway
    from memory.store import JsonlStore
    from .datasets import ExperienceDataset
    from .cycle import investigate
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--qualified-corpus',type=Path)
    args=parser.parse_args()
    from .cycle import gameplay_active
    if gameplay_active(): raise RuntimeError('offline learning unavailable during active gameplay')
    if not 1<=len(args.episode)<=4: raise ValueError('one to four preserved sessions required')
    # Fail before touching archives or creating stores if the destination exists.
    args.output.mkdir(parents=True,exist_ok=False)
    dataset=ExperienceDataset(EvidenceJournal(args.output/'learning-evidence.sqlite3'),args.output/'pixels')
    gateway=MemoryGateway(store=JsonlStore(args.output/'memory.jsonl'),
        evaluator=MemoryEvaluator(args.output/'evaluator.sqlite3'))
    from .archive_audit import audit
    audits=[]
    for root in args.episode:
        inspected=audit(root);audits.append(inspected)
        role=inspected['prior_partition']
        if role=='unknown': raise ValueError('unknown prior evidence use; declare through consume API before admission')
        consume(dataset,root/'game-01-evidence/meditation.json',source_episode=inspected['source_episode'],
            prior_use='consulted-test' if role=='test' else role)
    if args.qualified_corpus:qualify_corpus(dataset,args.qualified_corpus)
    report=investigate(dataset,gateway,diagnostics_only=True,max_jobs=4)
    report.update(archive_audits=audits,physical_authorization=False,
        acceptance='ALA-2 remains open; motion accuracy is not complete-game score improvement')
    with (args.output/'meditation-report.json').open('x') as stream:
        json.dump(report,stream,indent=2);stream.write('\n')
    dataset.journal.verify();dataset.journal.close()


if __name__=='__main__':main()
