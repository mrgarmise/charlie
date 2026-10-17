"""Phase adapter for the existing marathon and Executive, never a new chooser.

Commands are offline unless run is explicitly armed. Native camera/controller
preflight and restart permission remain owned by the existing player. An
interrupted gameplay block is never retried automatically on process restart.
"""
from __future__ import annotations

import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

from memory.evidence import EvidenceJournal, digest
from .datasets import sha
from .foundry import atomic_json

SCHEMA = 'charlie-gameplay-campaign-v1'
ROOT = Path(__file__).resolve().parents[1]


def source_identity():
    revision = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    names = subprocess.check_output(['git','ls-files','-z'], cwd=ROOT).decode().split('\0')
    files = {n: sha(ROOT/n) for n in names if n and (n.endswith('.py') or n.startswith('config/'))}
    # Include this adapter before its first publication too.
    files['learning/campaign.py'] = sha(__file__)
    return dict(revision=revision, runtime_sha256=digest(files))


def read(path):
    return json.loads(Path(path).read_text())


def configuration(state):
    return digest({k:state[k] for k in ('schema','source','notebook','blocks','games','proposal_id','policy')})


def create(directory, notebook, *, blocks=1, games=None, proposal_id=None, policy=None):
    directory, notebook = Path(directory).resolve(), Path(notebook).resolve()
    if type(blocks) is not int or not 1 <= blocks <= 33:
        raise ValueError('campaign requires 1..33 bounded three-game blocks')
    total=1 if proposal_id else (games if games is not None else blocks*3)
    if type(total) is not int or not 1 <= total <= 100 or (not proposal_id and total < 3):
        raise ValueError('practice requires 3..100 games; staged baseline request is one game')
    if proposal_id and games not in (None,1):
        raise ValueError('proposal cannot expand its one-game scope')
    if directory == notebook or directory in notebook.parents or notebook in directory.parents:
        raise ValueError('campaign and original notebook must be separate')
    if not (notebook/'learning-evidence.sqlite3').is_file():
        raise ValueError('existing original notebook required; do not initialize a replacement')
    if proposal_id and blocks != 1:
        raise ValueError('staged experiment is one baseline game, not a campaign grant')
    blocks=(total+2)//3
    state = dict(schema=SCHEMA, source=source_identity(), notebook=str(notebook),
        blocks=blocks, games=total, proposal_id=proposal_id, policy=str(Path(policy).resolve()) if policy else None,
        phase='ready', attempts=[], gates={g:'NOT YET DEMONSTRATED' for g in ('E1','P1','I1')},
        physical_authorization=False)
    if proposal_id:
        proposal(state)  # Validate original Executive request, never generate one.
    directory.mkdir(parents=True, exist_ok=False)
    atomic_json(directory/'campaign.json', state)
    return state


def proposal(state):
    with_journal = EvidenceJournal(Path(state['notebook'])/'learning-evidence.sqlite3', read_only=True)
    try:
        rows = [r for r in with_journal.category_records('event','gameplay_experiment_proposal')
                if r.data['payload'].get('proposal_id') == state['proposal_id']]
        if len(rows) != 1 or rows[0].data['producer'] != 'LearningExecutive':
            raise ValueError('original Executive gameplay proposal required')
        p = rows[0].data['payload']
        if p.get('trial_scope') != dict(game='robotron', maximum_games=1,
                maximum_candidate_shadows=len(p.get('alternatives', [])), candidate_activation=False):
            raise ValueError('only existing one-game baseline observation contract supported')
        if state.get('policy'):
            raise ValueError('staged baseline observation cannot activate a policy')
        if not p.get('hypothesis') or not p.get('measurements'):
            raise ValueError('frozen question and measurements required')
        for ref in ('search_id','evaluation_id','meditation_id','bookmark_id'):
            with_journal.get(p[ref])
        return dict(record_id=rows[0].id, **p)
    finally:
        with_journal.close()


def qualify_session(session):
    """Recheck all original recordings; software fixtures cannot qualify native use.

    This is lifecycle qualification only. Scores and learning remain unqualified.
    The operator still reviews actual playable starts before issuing expansion.
    """
    from experiments.ppal.game_evidence import preserve_game
    from experiments.ppal.marathon_robotron import safe_to_restart
    session = Path(session).resolve()
    doc = read(session/'session.json')
    if doc.get('camera_cleanup_error') or not doc.get('target_met'):
        raise ValueError('completed block and camera release required')
    games = doc.get('games', [])
    if len(games) != 3 or doc.get('completion_counts', {}).get('completed') != 3:
        raise ValueError('three consecutive complete native games required')
    journal = EvidenceJournal(doc['game_evidence_journal'], read_only=True)
    try:
        captures=[];camera_id=None;revision=None
        for index, entry in enumerate(games):
            record=journal.get(entry['durable_game_evidence']['record_id'])
            report=read(Path(entry['path'])/'report.json')
            if record.data['producer'] != 'independent-recording-boundary-validator':
                raise ValueError('independent completion validator required')
            result=preserve_game(journal, entry['path'], marathon=session,
                returncode=entry['returncode'], report=report)
            if result['classification'] != 'completed':
                raise ValueError('original game no longer qualifies')
            provenance=report.get('provenance', {})
            if (not provenance.get('git_commit') or provenance.get('simulation') or
                    provenance.get('fixture') or (report.get('sensory_preflight') or {}).get('status') != 'usable'):
                raise ValueError('native source identity and passed sensory preflight required')
            view=report['sensory_preflight'].get('camera_session',{})
            if index==0:camera_id=view.get('id');revision=provenance['git_commit']
            if (not camera_id or view.get('id')!=camera_id or view.get('reused') is not (index>0) or
                    provenance['git_commit']!=revision or provenance.get('dirty_worktree') is not False):
                raise ValueError('same qualified camera session and frozen clean revision required')
            if index and (not safe_to_restart(read(Path(games[index-1]['path'])/'report.json'),
                    games[index-1]['returncode'], capture_root=games[index-1]['path']) or
                    report.get('start_decision', {}).get('action') != 'restart' or
                    report.get('start_decision', {}).get('gameplay_verified') is not True or
                    report.get('start_decision', {}).get('start_commands') != 1):
                raise ValueError('verified automatic restart and playable next game required')
            captures.append(record.data['episode'])
        if len(set(captures)) != 3:
            raise ValueError('distinct captures required')
        return dict(session=str(session), session_sha256=sha(session/'session.json'), captures=captures,
            source_revision=revision,camera_session=camera_id,
            qualification='native lifecycle checks; operator observation still required', score='unqualified')
    finally:
        journal.close()


def arm(directory, *, hours=1., reliability_session=None, observed_native=False):
    """Operator command only. Grants no motion, deployment or firmware authority."""
    directory=Path(directory).resolve();state=read(directory/'campaign.json')
    import math
    if not math.isfinite(hours) or not 0 < hours <= 24:
        raise ValueError('finite authority duration in (0,24] hours required')
    if state['source'] != source_identity():
        raise ValueError('source changed since campaign freeze; prepare a new campaign')
    reliability=None
    if state['games'] > 3:
        if not reliability_session or not observed_native:
            raise ValueError('expansion requires reviewed native three-game qualification')
        reliability=qualify_session(reliability_session)
        if reliability['source_revision'] != state['source']['revision']:
            raise ValueError('native reliability must qualify the frozen campaign revision')
    if state['proposal_id']:proposal(state)
    policy_sha=None
    if state['policy']:
        from experiments.ppal.qualified_policy import load_policy
        load_policy(state['policy'], physical=True)
        policy_sha=sha(state['policy'])
    grant=dict(schema=SCHEMA, campaign=str(directory), source=state['source'], game='robotron',
        issued_at=time.time(), expires_at=time.time()+hours*3600,
        blocks=state['blocks'], proposal_id=state['proposal_id'], policy_sha256=policy_sha,
        configuration=configuration(state),
        source_of_authority='explicit operator campaign arm command',
        candidate_activation=False, servo=False, firmware=False, reliability=reliability)
    atomic_json(directory/'authority.json', grant)
    return grant


def check_authority(directory, state, frozen):
    try:
        grant=read(Path(directory)/'authority.json')
    except (OSError, ValueError) as exc:
        raise InterruptedError('campaign disarmed or authority unavailable') from exc
    if (grant != frozen or grant['campaign'] != str(Path(directory).resolve()) or
            grant['source'] != state['source'] or grant['game'] != 'robotron' or
            grant.get('configuration') != configuration(state) or
            time.time() >= grant['expires_at'] or grant['blocks'] != state['blocks'] or
            grant['proposal_id'] != state['proposal_id']):
        raise InterruptedError('campaign authority changed, expired or mismatched')


def command(directory, state, progress):
    target=min(3,state['games']-3*(len(state['attempts'])-1))
    args=[sys.executable,'-m','experiments.ppal.marathon_robotron', '--arm',
        '--developmental','--learning-projects','--play-first','--baseline-only',
        '--supervised-marathon','--marathon-progress',str(progress),
        '--root',str(Path(directory)/'runs'),'--learning-root',state['notebook'],
        '--campaign-notebook',state['notebook'],
        '--project-evidence',str(Path(state['notebook'])/'learning-project-evidence.sqlite3'),
        '--max-games','3','--qualified-games','3']
    if target < 3:
        # The original proposal requests one baseline game. Remaining attempts
        # are not authorized and must never be launched.
        args[args.index('--max-games')+1]=str(target)
        args[args.index('--qualified-games')+1]=str(target)
        args.append('--observation-block')
    elif len(state['attempts']) > 1 and not state.get('policy'):
        args.remove('--baseline-only')  # Existing Executive/chooser may select.
    if state['policy']:args.extend(['--learned-policy',state['policy']])
    return args


def deliver_observation(state, entry):
    """Bind a completed acquisition to Charlie's original request, not a verdict."""
    if not state['proposal_id']:return None
    p=proposal(state);session=Path(entry['session']);doc=read(session/'session.json')
    notebook=Path(state['notebook'])
    with (notebook/'offline.lock').open('a') as owner:
        fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
        journal=EvidenceJournal(notebook/'learning-evidence.sqlite3')
        try:
            content=dict(category='gameplay_experiment_delivery',proposal_id=p['proposal_id'],
                project_id=p['project_id'],session=str(session.resolve()),
                completion_records=[g['durable_game_evidence'] for g in doc['games']],
                source_question=p['original_question'],required_measurements=p['measurements'],
                candidate_ids=[a['identifier'] for a in p['alternatives']],
                status='OBSERVATIONS_DELIVERED_AWAITING_INDEPENDENT_MEASUREMENTS',
                hypothesis_resolved=False,candidate_activated=False,physical_authorization=False,
                next_direction='Existing acquisition and independent corpus qualification must validate identities, trajectories and score before the retained temporal experiment can resolve')
            old=next((r for r in journal.category_records('event','gameplay_experiment_delivery')
                if r.data['payload']==content),None)
            record=old or journal.append('event',content,episode=journal.get(p['record_id']).data['episode'],
                sources=[p['record_id']],producer='existing-marathon-acquisition-handoff',version=SCHEMA)
            return record.id
        finally:journal.close()


def synchronize_projects(notebook):
    """Carry retained Executive outcomes into the existing marathon projection.

    Called only while owning the original notebook lock. Immutable record IDs
    survive both directions of the existing handoff; transfers are not new
    investigations or independent experience.
    """
    notebook=Path(notebook)
    source=EvidenceJournal(notebook/'learning-evidence.sqlite3',read_only=True)
    target=EvidenceJournal(notebook/'learning-project-evidence.sqlite3')
    try:
        added=target.merge_from(source)
        return dict(added_records=len(added),source_record_ids_digest=digest([r.id for r in source.records()]),
            independent_new_experience=False)
    finally:source.close();target.close()


def run(directory, *, armed=False, supervisor=None, reflector=None):
    from experiments.ppal.progress_supervision import supervise
    from experiments.ppal.marathon_robotron import reflect_marathon
    from types import SimpleNamespace
    directory=Path(directory).resolve();path=directory/'campaign.json'
    supervisor=supervisor or supervise;reflector=reflector or reflect_marathon
    with (directory/'campaign.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=read(path)
        if state['source'] != source_identity():
            raise ValueError('frozen campaign source changed')
        if state['phase']=='playing':
            # A crash might follow START. Never infer completion or replay it.
            state.update(phase='blocked', reason='Interrupted gameplay block: reconcile original evidence; no automatic retry')
            atomic_json(path,state);return state
        if state['phase'] in ('blocked','completed'):
            return state
        try:
            while len(state['attempts']) < state['blocks'] or state['phase']=='reflecting':
                if state['phase']=='reflecting':
                    entry=state['attempts'][-1];session=Path(entry['session'])
                    entry['observation_delivery']=deliver_observation(state,entry)
                    result=reflector(session, SimpleNamespace(learning_root=Path(state['notebook']),
                        campaign_notebook=Path(state['notebook']),
                        project_evidence=Path(state['notebook'])/'learning-project-evidence.sqlite3',
                        reflection_turns=12,ala_budget=10.,processing_budget=300.))
                    entry['reflection']=result
                    if result.get('phase') != 'checkpointed':
                        state['reason']='Retained offline work must resume before another gameplay block'
                        atomic_json(path,state);return state
                    state['phase']='ready';atomic_json(path,state)
                    continue
                if not armed:
                    raise InterruptedError('explicit --arm and operator grant required for gameplay')
                if state['source'] != source_identity():
                    raise ValueError('frozen source changed between blocks')
                frozen=read(directory/'authority.json')
                check_authority(directory,state,frozen)
                if state['policy']:
                    if sha(state['policy']) != frozen['policy_sha256']:
                        raise ValueError('authorized policy manifest changed')
                    from experiments.ppal.qualified_policy import load_policy
                    load_policy(state['policy'],physical=True)
                if state['proposal_id']:proposal(state)
                index=len(state['attempts'])+1;progress=directory/f'block-{index:03d}-progress.json'
                entry=dict(index=index,progress=str(progress),source=state['source'],
                    proposal_id=state['proposal_id'],policy_sha256=frozen['policy_sha256'])
                # Commit launch intent before the worker can issue START.
                state['attempts'].append(entry);state['phase']='playing';atomic_json(path,state)
                # The ordinary Executive lock excludes a second notebook owner.
                # Release it before handing work back to the existing lifecycle.
                with (Path(state['notebook'])/'offline.lock').open('a') as owner:
                    fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    entry['retained_executive_handoff']=synchronize_projects(state['notebook'])
                    atomic_json(path,state)
                    rc=supervisor(command(directory,state,progress), progress, processing=90.,
                        on_poll=lambda:check_authority(directory,state,frozen))
                entry['returncode']=rc
                final=read(progress)
                if rc or not final.get('gameplay_finished') or not final.get('session'):
                    raise ValueError('gameplay block interrupted or camera release unconfirmed')
                entry['session']=final['session'];doc=read(Path(entry['session'])/'session.json')
                expected=min(3,state['games']-3*(index-1))
                if (not doc.get('target_met') or len(doc.get('games',[])) != expected or
                        doc.get('completion_counts',{}).get('completed') != expected or doc.get('camera_cleanup_error')):
                    raise ValueError('qualified game target unmet; preserve partial attempts')
                state['phase']='reflecting';atomic_json(path,state)
            state.update(phase='completed',reason='Bounded campaign executed; learning, scores and native acceptance require independent review')
        except (KeyboardInterrupt,InterruptedError,ValueError,OSError) as exc:
            state.update(phase='blocked',reason=type(exc).__name__+': '+str(exc))
        finally:
            state['physical_authorization']=False
            atomic_json(path,state)
        return state


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('directory',type=Path);p.add_argument('--notebook',type=Path,required=True)
    p.add_argument('--blocks',type=int,default=1);p.add_argument('--games',type=int);p.add_argument('--proposal-id');p.add_argument('--policy',type=Path)
    p=sub.add_parser('arm');p.add_argument('directory',type=Path);p.add_argument('--hours',type=float,default=1.)
    p.add_argument('--reliability-session',type=Path);p.add_argument('--observed-native-three',action='store_true')
    p=sub.add_parser('run');p.add_argument('directory',type=Path);p.add_argument('--arm',action='store_true')
    p=sub.add_parser('disarm');p.add_argument('directory',type=Path)
    args=parser.parse_args(argv)
    if args.action=='prepare':result=create(args.directory,args.notebook,blocks=args.blocks,games=args.games,proposal_id=args.proposal_id,policy=args.policy)
    elif args.action=='arm':result=arm(args.directory,hours=args.hours,reliability_session=args.reliability_session,observed_native=args.observed_native_three)
    elif args.action=='disarm':
        (args.directory/'authority.json').unlink(missing_ok=True);result=dict(status='disarmed')
    else:result=run(args.directory,armed=args.arm)
    print(json.dumps(result,indent=2))
    if args.action=='run' and result['phase']!='completed':raise SystemExit(2)

if __name__=='__main__':main()
