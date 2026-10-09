"""Autonomous Robotron marathon orchestrator.

Each game remains an independent timestamped episode.  This module never
concatenates tracks, frames, or reports across game boundaries.

It wraps the known-good single-game player as a subprocess, retries START by
starting another independent attempt, evaluates completed live reports, and
enters per-episode/cross-episode meditation after repeated failure to establish
gameplay (normally exhausted credits).
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA="charlie-robotron-marathon-v1"

def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def run(cmd):
    print("+", " ".join(map(str,cmd)), flush=True)
    return subprocess.run(cmd, check=False).returncode


def run_bounded(cmd, timeout=None):
    """Compatibility callable: timeout is now a no-progress bound, not game age."""
    from .progress_supervision import supervise
    game = Path(cmd[cmd.index('--output')+1])
    print('+', ' '.join(map(str,cmd)),flush=True)
    # Invoke the supervised child directly; this runner is its independent parent.
    return supervise([*cmd, '--supervised-child'], game.parent/(game.name+'-progress.json'),
                     silence=timeout or 30., processing=90.)


class ProcessingYield(Exception):
    """Checkpoint after productive work, not an episode failure or verdict."""

class ProcessingDeferred(RuntimeError):
    """Bounded productive processing needs another offline invocation."""


def preserve_processing_artifacts(output):
    """Retain prior diagnostic/config bytes before resuming native processing.

    SQLite history remains append-only; source captures are never rewritten.
    Snapshots are correlated processing history, not independent experience.
    """
    import hashlib
    output=Path(output)
    for path in [*output.glob('*.json'),*output.glob('*.md')]:
        data=path.read_bytes()
        target=output/'processing-history'/(path.name+'-'+hashlib.sha256(data).hexdigest())
        target.parent.mkdir(exist_ok=True)
        if target.exists():
            if target.read_bytes()!=data:raise ValueError('processing history integrity mismatch')
        else:target.write_bytes(data)


def process_supervised(game, output, gateway, commitments, plan=None, executive=None, budget=300., chunks=3, ala_root=None, ala_budget=60.,ala_authority=None, defer_meditation=False):
    from .progress_supervision import supervise
    output.mkdir(parents=True, exist_ok=True)
    if defer_meditation:preserve_processing_artifacts(output)
    config = dict(game=str(game), output=str(output), evaluator=str(gateway.evaluator.path),
                  outbox=str(gateway.store.path), project=gateway.project, session=gateway.session,
                  commitments=str(commitments.path), plan=plan,
                  project_evidence=str(executive.journal.path) if executive else None,
                  progress=str(output/'processing-progress.json'), work_budget=budget,
                  ala_root=str(ala_root) if ala_root else None, ala_budget=ala_budget,ala_authority=ala_authority,
                  defer_meditation=defer_meditation)
    # Paths and already committed plan only; no credentials or new hypotheses.
    path = output/'processing-config.json'
    write_session(path, config)
    for attempt in range(chunks):
        rc = supervise([sys.executable,'-m','experiments.ppal.process_robotron_episode',str(path)],
                       config['progress'], processing=60., budget=budget+10.)
        write_session(output/f'processing-chunk-{attempt+1:02d}.json',dict(
            supervisor=load_report(output/'processing-progress-supervisor.json'),
            resources=load_report(output/'processing-resources.json')))
        if rc == 0: break
        if rc != 75:
            raise RuntimeError(f'between-game processing stopped (rc={rc}); retained partial evidence at {output}')
    else:
        raise ProcessingDeferred(f'between-game processing deferred after {chunks} productive chunks; resume {path}; no new START authorized')
    return load_report(output/'between-game.json')


def process_completed_episode(game, output, gateway, commitments, plan=None, executive=None, progress=None, work_budget=None, ala_root=None, ala_budget=60.,ala_authority=None, defer_meditation=False):
    """Existing E/E + Reflection + Meditation + Evaluator, between games only."""
    from memory.evidence import EvidenceJournal
    from .episode_evidence import import_episode, derive_episode, summarize
    from .reflect_robotron import reflect_evidence, reflect_actuator_evidence, reflect_learning_projects, reflect_episode_context
    from .experiment_return import resolve_experiment
    from .meditate_robotron import meditate, quality
    from .evaluate_robotron_shadow import evaluate
    output.mkdir(parents=True,exist_ok=True)
    if defer_meditation:preserve_processing_artifacts(output)
    import resource
    began=time.monotonic()
    stage_resources={}
    stage_times = {}
    last_progress = [0.]
    def pulse():
        if work_budget is not None and time.monotonic()-began >= work_budget:
            raise ProcessingYield('productive work budget reached; committed units retained')
        if progress and time.monotonic()-last_progress[0] >= 1.:
            progress.update(processing_units=progress.data.get('processing_units',0)+1)
            last_progress[0] = time.monotonic()
    def stage(name):
        now = time.monotonic()
        stage_times[name] = now
        usage=resource.getrusage(resource.RUSAGE_SELF)
        stage_resources[name]=dict(elapsed=now-began,cpu=usage.ru_utime+usage.ru_stime,max_rss_kib=usage.ru_maxrss)
        if progress: progress.update(stage=name)
        print(f"{'OFFLINE EPISODE' if defer_meditation else 'BETWEEN GAME'}: {name}", flush=True)
    journal=EvidenceJournal(output/'evidence.sqlite3', on_progress=pulse)
    try:
        stage('import')
        episode=import_episode(game,journal)
        # Resolve live commitment first. Replay diagnostics must not masquerade
        # as outcomes of the pre-game experiment.
        stage('resolve_experiment')
        resolution=None
        if plan:
            if (game/'report.json').is_file():
                resolution=resolve_experiment(game,journal,episode,commitments,plan,gateway)
            else:
                retained=commitments.resolution_for(plan['prediction_id'])
                retained=retained or commitments.resolve(plan['prediction_id'],sources=(),result='unresolved',
                    reason='child ended without report; preserved partial evidence cannot resolve experiment')
                resolution=dict(prediction_id=plan['prediction_id'],resolution_id=retained.id,
                    result=retained.data['payload']['result'],reason=retained.data['payload']['reason'],
                    attempted=None,score_attribution=None)
        assessment = None
        if executive is not None and plan and plan.get('project_id') and resolution:
            assessment=executive.record_result(plan['project_id'],plan,resolution,commitments,episode=episode)
        stage('reconcile_perception')
        reconciliation=gateway.evaluator.reconcile_perception(journal,game)
        stage('derive')
        derive_episode(game,journal,episode)
        stage('reflection')
        reflection=reflect_evidence(journal,episode,gateway)
        proposals=reflect_actuator_evidence(game,journal,episode,gateway)
        project_updates = None
        if executive is not None:
            project_proposals = reflect_learning_projects(journal, episode, proposals)
            ids=[]
            for proposal in project_proposals:
                ids.append(executive.propose(proposal['proposal'],journal,[proposal['evidence_id']]))
                pulse()
            project_updates = dict(proposed=ids, assessment=assessment)
        report=load_report(game/'report.json')
        shadow = evaluate(report) if report else {'status':'unavailable; no finalized report', 'boundary':'unknown'}
        (output/'shadow-evaluation.json').write_text(json.dumps(shadow,indent=2)+'\n')
        stage('meditation')
        meditation=None
        if defer_meditation and (output/'meditation.json').is_file():
            import hashlib
            meditation=load_report(output/'meditation.json')
            if (not meditation or not (game/'tracks.json').is_file()
                    or meditation.get('source_sha256')!=hashlib.sha256((game/'tracks.json').read_bytes()).hexdigest()):
                raise ValueError('retained meditation source mismatch; preserve original finding')
        if not defer_meditation and (game/'tracks.json').exists():
            tracks=json.loads((game/'tracks.json').read_text()).get('tracks',[])
            import hashlib
            source_hash=hashlib.sha256((game/'tracks.json').read_bytes()).hexdigest()
            cached=load_report(output/'meditation.json')
            if cached and cached.get('source_sha256')==source_hash and cached.get('version')=='reconstruction-v1':
                meditation=cached; pulse()
            else:
                rebuilt,history,merges=meditate(tracks,on_progress=pulse)
                meditation=dict(source=str(game/'tracks.json'),source_sha256=source_hash,version='reconstruction-v1',history=history,merges=merges,quality=quality(rebuilt),note='offline interpreted IDs; not canonical identity or policy advice')
            (output/'meditation.json').write_text(json.dumps(meditation,indent=2)+'\n')
        stage('context_reflection')
        context=reflect_episode_context(game,journal,episode,gateway,plan=plan,resolution=resolution,meditation=meditation)
        (output/'learning-report.md').write_text(
            f"Episode: {episode}\n\nObjective: official game score. Experiment: BODY={(plan or {}).get('body','UNKNOWN')} FIRE={(plan or {}).get('fire','UNKNOWN')}; expected={(plan or {}).get('expected','none justified')}.\n\n"
            f"Prediction resolution: {(resolution or {}).get('result','no commitment')}; {(resolution or {}).get('reason','no resolving evidence')}.\n\n"
            f"Resolving evidence: {(resolution or {}).get('canonical_response_evidence','NONE')}; resolution={(resolution or {}).get('resolution_id','NONE')}. Memory update: {(resolution or {}).get('belief_change','none')}.\n\n"
            f"Identity reports: {context['identity_samples']} (provisional remains provisional).\n\n"
            f"Score observations: {context['score_observations']}. Causal performance improvement: UNKNOWN.\n\n"
            f"Meditation: {context['meditation_status']}. Replay tests are correlated diagnostics from one episode.\n\nOpen questions:\n\n"
            +''.join('- '+q['question']+'\n' for q in context['questions']))
        ala=None
        if ala_root is not None and executive is not None:
            stage('autonomous_learning')
            from learning.cycle import postgame_learning
            ala=postgame_learning(game,journal,episode,context,gateway,executive,ala_root,budget_seconds=ala_budget,on_progress=pulse,deployment_authority=ala_authority)
        result={'autonomous_learning':ala,'episode':episode,'resolution':resolution,'reflection':reflection,
                'proposals':proposals,'learning_context':context,'meditation':str(output/'meditation.json') if meditation else None,
                'evidence':summarize(journal,episode)}
        if executive is not None:
            result['learning_projects'] = project_updates
        stage('complete')
        result['processing_timing'] = stage_times
        result['processing_resources'] = stage_resources
        (output/'between-game.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    finally:
        usage=resource.getrusage(resource.RUSAGE_SELF)
        write_session(output/'processing-resources.json',dict(elapsed=time.monotonic()-began,
            cpu_seconds=usage.ru_utime+usage.ru_stime,max_rss_kib=usage.ru_maxrss,stages=stage_resources,
            database_bytes={p.name:p.stat().st_size for p in output.glob('*.sqlite3')}))
        journal.close()


def developmental_marathon(args, *, driver=run_bounded, gateway=None):
    """Bounded runner with optional project continuity, between games only."""
    from collections import Counter
    from memory.evidence import EvidenceJournal
    from memory.gateway import MemoryGateway
    from .experiment_return import select_experiment
    gateway=gateway or MemoryGateway()
    authority_path=getattr(args,'ala_deployment_authority',None)
    authority=json.loads(Path(authority_path).read_text()) if authority_path else None
    developmental = getattr(args,'developmental',True)
    session=args.root/f'{"development" if developmental else "marathon"}-{stamp()}'
    session.mkdir(parents=True,exist_ok=False)
    commitments=EvidenceJournal(session/'experiment-evidence.sqlite3')
    project_journal = None
    executive = None
    if getattr(args, 'learning_projects', False):
        from memory.learning_projects import LearningExecutive
        # Shared durable operational evidence survives new marathon directories.
        path = getattr(args, 'project_evidence', None) or gateway.evaluator.path.with_name('learning-project-evidence.sqlite3')
        project_journal = EvidenceJournal(path)
        executive = LearningExecutive(project_journal, gateway)
    doc={'schema':'charlie-developmental-marathon-v1','status':'running','games':[],
         'objective':'official_game_score','policy':'existing policy plus at most one explicit actuator experiment',
         'seed':str(args.seed_episode) if args.seed_episode else None}
    play_first=getattr(args,'play_first',False)
    doc['development_timing']='after_marathon' if play_first else 'between_games'
    doc['phase']='gameplay'
    doc['learning_project_evidence']=str(project_journal.path) if project_journal else None
    doc['learning_root']=str(getattr(args,'learning_root',None) or
        (Path.home()/'.local/share/charlie/development' if play_first else gateway.evaluator.path.with_name('autonomous-learning')))
    plan=None
    # Tests may inject an in-process driver and gateway. Physical default always
    # supervises offline work in a separate process with existing durable stores.
    if driver is run_bounded:
        def processor(*values, **options):
            return process_supervised(*values, **options, budget=getattr(args,'processing_budget',300.),
                ala_root=(getattr(args,'learning_root',None) or gateway.evaluator.path.with_name('autonomous-learning')) if getattr(args,'ala_learning',False) else None,
                ala_budget=getattr(args,'ala_budget',60.),ala_authority=authority)
    else:
        processor = process_completed_episode
    primary_claim=None
    if play_first:
        from learning.cycle import gameplay_session
        primary_claim=gameplay_session()
        primary_claim.__enter__()
    try:
        if args.seed_episode:
            if play_first:
                doc['seed_processing']={'status':'deferred','path':str(args.seed_episode.resolve())}
            else:
                doc['seed_processing']=processor(args.seed_episode,session/'seed-evidence',gateway,commitments,executive=executive)
        for index in range(1,args.max_games+1):
            game=session/f'game-{index:02d}'
            selection = None
            context = None
            if executive:
                selection = executive.select(methods={'actuator-response'},
                    resources={'camera-evidence', 'actuator-experiment-slot'}, authorized_methods={'actuator-response'})
                if selection['project']:
                    context = executive.chooser_context(selection['project']['id'])
            plan = None if not developmental or (executive and context is None) else select_experiment(
                gateway,commitments,game,horizon_seconds=(args.game_seconds or 120.)+120.,project_context=context)
            plan_path=session/f'game-{index:02d}-experiment.json'
            if plan:write_session(plan_path,plan)
            reason=plan['reason'] if plan else 'no justified experiment yet; existing policy only'
            print(f'DEVELOPMENT GAME {index}/{args.max_games}: {reason}',flush=True)
            write_session(session/'session.json',doc)
            cmd=[sys.executable,'-m','experiments.ppal.play_robotron','--arm',
                 '--focus',str(args.focus),'--output',str(game)]
            if developmental:cmd.extend(['--bootstrap-body-fire','--recalibrate'])
            if args.game_seconds is not None:cmd.extend(['--diagnostic-seconds',str(args.game_seconds)])
            if plan:cmd.extend(['--experiment-plan',str(plan_path)])
            semantic_manifest=getattr(args,'learned_semantics',None)
            if semantic_manifest is None and authority:
                candidate_root=getattr(args,'learning_root',None) or gateway.evaluator.path.with_name('autonomous-learning')
                candidate_manifest=Path(candidate_root)/'semantic-activation.json'
                if candidate_manifest.exists():semantic_manifest=candidate_manifest
            if semantic_manifest:cmd.extend(['--learned-semantics',str(semantic_manifest)])
            if executive:
                viewer_context = session/f'game-{index:02d}-observer-context.json'
                write_session(viewer_context, {'episode':str(game.resolve()), 'project':selection['project']})
                cmd.extend(['--observer-context', str(viewer_context)])
            if play_first:
                # Bookmark before the child: interrupted captures remain discoverable.
                doc['games'].append(dict(path=str(game),experiment=plan,status='recording',
                    reason_for_experiment=reason))
                write_session(session/'session.json',doc)
            rc=driver(cmd,30.)
            report=load_report(game/'report.json')
            entry={'path':str(game),'returncode':rc,'result':report.get('result') if report else 'missing report',
                   'experiment':plan,'reason_for_experiment':reason,
                   'supervision':load_report(game.parent/(game.name+'-progress-supervisor.json'))}
            if executive:
                entry['project_selection'] = selection
            if play_first:doc['games'][-1]=entry
            else:doc['games'].append(entry)
            write_session(session/'session.json',doc)
            if report:
                entry['score_evidence']=report.get('score_summary',{'self_score':report.get('score'),'status':report.get('score_status','unknown')})
                entry['score_attribution']='unknown; accepted reading is not independently verified score'
                entry['self_status']=dict(Counter(s.get('identity_status','unknown') for s in report.get('steps',[])))
                entry['between_game']=({'status':'deferred','reason':'play first; original evidence and commitment retained'} if play_first else
                    processor(game,session/f'game-{index:02d}-evidence',gateway,commitments,plan,executive))
            else:
                entry['between_game']={'status':'unknown; no complete report'}
                if plan and not play_first:
                    resolution=commitments.resolve(plan['prediction_id'],sources=(),result='unresolved',reason='child ended without report')
                    entry['resolution_id']=resolution.id
                    if executive and plan.get('project_id'):
                        executive.record_result(plan['project_id'], plan,
                            dict(resolution_id=resolution.id, result='unresolved', reason='child ended without report'),
                            commitments, episode='missing-report:'+str(game))
                if game.exists() and not play_first:
                    partial = processor(game, session/f'game-{index:02d}-partial-evidence', gateway,
                                        commitments, None, executive)
                    entry['between_game']['partial_evidence'] = partial
            resolution=(entry['between_game'].get('resolution') or {}).get('result','no prediction')
            before=(entry['between_game'].get('resolution') or {}).get('memory_evaluation_before',{})
            after=(entry['between_game'].get('resolution') or {}).get('memory_evaluation_after',{})
            score=(entry.get('score_evidence') or {}).get('self_score')
            print(f"GAME {index}: score evidence={score}; SELF={entry.get('self_status','UNKNOWN')}; "
                  f"experiment attempted={(entry['between_game'].get('resolution') or {}).get('attempted',False)}; "
                  f"prediction={plan['prediction_id'][:12] if plan else 'NONE'}; resolution={resolution}; "
                  f"memory={before.get('priority','UNKNOWN')}->{after.get('priority','UNKNOWN')} "
                  f"({after.get('status','UNKNOWN')}); "
                  f"belief={(entry['between_game'].get('resolution') or {}).get('belief_change','none')}",flush=True)
            if executive:
                project_state = executive.projects().get(context['project_id'], {}) if context else {}
                print(f"PROJECT: {context['project_id'][:12] if context else 'NONE'}; "
                      f"goal={project_state.get('goal','UNKNOWN')}; status={project_state.get('status','UNKNOWN')}; "
                      f"selection={selection['reason']}; progress={project_state.get('progress','UNKNOWN')}; "
                      f"next={project_state.get('next_direction','no justified experiment yet')}", flush=True)
            write_session(session/'session.json',doc)
            if rc==124:
                doc['status']='child_timeout';break
            if index>=args.max_games:
                doc['status']='bounded_attempts_complete' if safe_to_restart(report,rc,capture_root=game) else 'unverified_episode_boundary'
                break
            entry['recording_readiness']=recording_readiness(game,report)
            write_session(session/'session.json',doc)
            if not safe_to_restart(report,rc,capture_root=game):
                doc['status']='unverified_episode_boundary'
                print('DEVELOPMENT STOP: no confirmed game-over evidence; no further START',flush=True)
                break
            time.sleep(args.retry_wait)
    except KeyboardInterrupt:
        doc['status']='interrupted'
    except ProcessingDeferred as exc:
        doc['status']='processing_deferred'
        doc['error']=str(exc)
        print(f'DEVELOPMENT PAUSED: {exc}',flush=True)
    except Exception as exc:
        doc['status']='between_game_failure'
        doc['error']=f'{type(exc).__name__}: {exc}'
        print(f"DEVELOPMENT STOP: {doc['error']}",flush=True)
    finally:
        if primary_claim:primary_claim.__exit__(None,None,None)
        if plan and not play_first and not any(r.data['payload']['prediction_id']==plan['prediction_id'] for r in commitments.records('resolution')):
            try:
                unresolved=commitments.resolve(plan['prediction_id'],sources=(),result='unresolved',
                    reason='orchestration stopped without sufficient resolving evidence')
                doc['unresolved_on_stop']=unresolved.id
                if executive and plan.get('project_id'):
                    executive.record_result(plan['project_id'], plan,
                        dict(resolution_id=unresolved.id, result='unresolved',
                             reason='orchestration stopped without sufficient resolving evidence'),
                        commitments, episode='orchestration-stop:'+plan['scope'])
            except Exception as exc:
                doc['resolution_persistence_error']=f'{type(exc).__name__}: {exc}'
        write_session(session/'session.json',doc)
        commitments.close()
        if project_journal:
            doc['learning_project_evidence'] = str(project_journal.path)
            doc['learning_projects'] = executive.projects()
            write_session(session/'session.json',doc)
            project_journal.close()
        print(f"DEVELOPMENT COMPLETE: {doc['status']}; attempts={len(doc['games'])}; {session}",flush=True)
    if play_first and doc['status']!='interrupted':
        doc['reflection']=reflect_marathon(session,args,gateway=gateway)
    return doc

def reflect_marathon(session, args, *, gateway=None, processor=None, development=None):
    """Resume the existing offline adapters, then the normal Executive lifecycle.

    This is a phase handoff, never an agenda selector or controller owner.
    Original session.json and captures are read-only during offline recovery.
    """
    import fcntl
    from memory.evidence import EvidenceJournal
    from memory.gateway import MemoryGateway
    from memory.learning_projects import LearningExecutive
    from memory.episode_identity import inspect_capture
    from learning.cycle import gameplay_active
    from learning.datasets import sha
    from learning.lifecycle import run as develop
    session=Path(session).resolve()
    doc=load_report(session/'session.json')
    if not doc:raise ValueError('existing marathon session.json required')
    if gameplay_active():raise RuntimeError('reflection unavailable during active gameplay')
    gateway=gateway or MemoryGateway()
    processor=processor or process_supervised
    development=development or develop
    path=session/'reflection-progress.json'
    with (session/'reflection.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=load_report(path) or dict(schema='charlie-marathon-reflection-v1',episodes={},
            learning_root=str(getattr(args,'learning_root',None) or doc.get('learning_root') or
                gateway.evaluator.path.with_name('autonomous-learning')),
            project_evidence=str(getattr(args,'project_evidence',None) or doc.get('learning_project_evidence') or
                gateway.evaluator.path.with_name('learning-project-evidence.sqlite3')),
            physical_authorization=False)
        # A resume cannot silently relocate durable Executive state.
        for key in ('learning_root','project_evidence'):
            requested=getattr(args,key,None)
            if requested and Path(requested).resolve()!=Path(state[key]).resolve():
                raise ValueError('resume must retain '+key)
        commitments=EvidenceJournal(session/'experiment-evidence.sqlite3')
        projects=EvidenceJournal(state['project_evidence'])
        executive=LearningExecutive(projects,gateway)
        state['phase']='importing';write_session(path,state)
        roots=[]
        entries=list(doc.get('games',[]))
        if doc.get('seed'):
            entries.insert(0,dict(path=doc['seed'],experiment=None,seed=True))
        try:
            for entry in entries:
                game=Path(entry['path']).resolve()
                if not game.exists():
                    state['episodes'][str(game)]=dict(status='blocked',reason='original capture unavailable')
                    write_session(path,state);continue
                try:
                    identity=inspect_capture(game)
                    binding={k:identity[k] for k in ('capture_id','manifest_id','content_id','artifacts')}
                except (ValueError,OSError) as exc:
                    state['episodes'][str(game)]=dict(status='blocked',reason=str(exc))
                    write_session(path,state);continue
                roots.append(game)
                output=session/('seed-evidence' if entry.get('seed') else game.name+'-evidence')
                prior=state['episodes'].get(str(game),{})
                if prior.get('source_binding') and prior['source_binding']!=binding:
                    raise ValueError('reflection source changed after checkpoint')
                if prior.get('status')=='completed':
                    if sha(output/'between-game.json')!=prior['result_sha256']:
                        raise ValueError('completed reflection receipt changed')
                    with_journal=EvidenceJournal(output/'evidence.sqlite3',read_only=True)
                    with_journal.close()
                    continue
                state['episodes'][str(game)]=dict(status='processing',source_binding=binding,
                    boundary='confirmed' if safe_to_restart(load_report(game/'report.json'),entry.get('returncode',0),capture_root=game)
                        else 'uncertain; not independently confirmed complete',
                    complete_game_score='requires independent qualification')
                write_session(path,state)
                try:
                    # Expensive meditation belongs to the Executive below, not this importer.
                    processor(game,output,gateway,commitments,entry.get('experiment'),executive,
                        **(dict(budget=getattr(args,'processing_budget',300.)) if processor is process_supervised else {}),
                        defer_meditation=True)
                except (ProcessingDeferred,ProcessingYield) as exc:
                    state['episodes'][str(game)]['status']='yielded'
                    state['phase']='yielded';state['reason']=str(exc)
                    write_session(path,state);return state
                state['episodes'][str(game)].update(status='completed',result_sha256=sha(output/'between-game.json'))
                write_session(path,state)
            # Exact project history, including unresolved experiments, enters the
            # existing normal notebook. No new independent experience is inferred.
            notebook=Path(state['learning_root'])
            if any(notebook.resolve()==r or r in notebook.resolve().parents or notebook.resolve() in r.parents for r in roots):
                raise ValueError('normal notebook must be separate from original captures')
            notebook.mkdir(parents=True,exist_ok=True)
            from memory.evidence import digest
            handoff=dict(schema='charlie-marathon-handoff-v1',session=str(session),
                episodes=[str(r) for r in roots],project_evidence=str(projects.path.resolve()),
                retained_project_ids=[r.id for r in projects.records()],physical_authorization=False)
            handoff_path=notebook/'marathon-handoffs'/(digest(handoff)+'.json')
            handoff_path.parent.mkdir(exist_ok=True)
            write_session(handoff_path,handoff)
            state['handoff']=str(handoff_path)
            with (notebook/'offline.lock').open('a') as notebook_lock:
                try:fcntl.flock(notebook_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:
                    state.update(phase='executive_owned',
                        development_status=str(notebook/'development-status.json'),
                        reason='Existing normal Executive owns notebook; durable acquisition handoff awaits its next turn')
                    write_session(path,state);return state
                target=EvidenceJournal(notebook/'learning-evidence.sqlite3')
                try:target.merge_from(projects)
                finally:target.close()
            state['phase']='executive';write_session(path,state)
            development(notebook,roots,budget_seconds=min(getattr(args,'ala_budget',10.),60.),
                interval=.05,turns=getattr(args,'reflection_turns',12),offline_authority=None)
            state['phase']='checkpointed'
            state['development_status']=str(notebook/'development-status.json')
            state['reason']='Executive retains unfinished work; reflection may resume without gameplay'
            write_session(path,state)
            return state
        except BaseException as exc:
            state['phase']='interrupted' if isinstance(exc,KeyboardInterrupt) else 'blocked'
            state['reason']=type(exc).__name__+': '+str(exc);write_session(path,state)
            raise
        finally:
            commitments.close();projects.close()


def load_report(path):
    try: return json.loads(path.read_text())
    except (OSError, ValueError): return None

def established_gameplay(report):
    """Conservative: the existing player must actually have produced game steps."""
    if not report: return False
    steps=report.get("steps") or []
    return bool(report.get("armed") and report.get("acquisition") and
                any("action" in s for s in steps))

def recording_readiness(root,report):
    """Between-game barrier; no controller or permission authority."""
    from memory.episode_identity import verify_recording_completion,inspect_capture
    try:
        if not report or report.get('recording_error') or report.get('recording_pipeline',{}).get('writer_alive'):
            raise ValueError('recording failure or live previous writer')
        if report.get('score_summary',{}).get('worker_finished') is False:
            raise ValueError('previous score instrumentation writer unfinished')
        state=verify_recording_completion(root)
        if state is None:raise ValueError('no verified new recording receipt')
        identity=inspect_capture(root)
        if identity.get('status')=='quarantined':raise ValueError('capture identity quarantined')
        return dict(status='ready',completion_sha256=state['completion']['sha256'],
            incident_requests='durably resolved',previous_writer='terminated and source sealed',
            complete_game_score='separate qualification required')
    except (ValueError,OSError,KeyError) as exc:
        return dict(status='blocked',reason=str(exc),physical_authorization=False)


def safe_to_restart(report, returncode=0,*,capture_root=None):
    """Only an explicit, evidenced terminal screen may authorize another START."""
    if returncode != 0 or not report:
        return False
    if capture_root is not None and recording_readiness(capture_root,report)['status']!='ready':return False
    if capture_root is None and report.get('recording_pipeline'):return False
    end = report.get('episode_end', {})
    evidence = end.get('evidence') or {}
    terminal=(report.get('result')=='GAME OVER' and end.get('state')=='game_over' and end.get('confirmed') is True
        and evidence.get('not_gameplay_streak',0)>=8 and (evidence.get('screen') or {}).get('state')=='not_gameplay'
        and (evidence.get('screen') or {}).get('phase') in ('startable','terminal','title'))
    causal=evidence.get('rule')=='persistent_not_gameplay_plus_no_controlled_self' and evidence.get('agency_failures',0)>=1
    visual=(evidence.get('rule')=='gameplay_terminal_attract_sequence' and evidence.get('established_gameplay') is True
        and evidence.get('terminal_corroborated') is True and evidence.get('attract_streak',0)>=3
        and len(set(evidence.get('terminal_capture_timestamps',[])))>=3
        and len(set(evidence.get('attract_capture_timestamps',[])))>=3
        and (evidence.get('screen') or {}).get('phase')=='startable')
    title=(evidence.get('rule')=='established_gameplay_then_verified_title'
        and evidence.get('established_gameplay') is True and evidence.get('attract_streak',0)>=3
        and len(set(evidence.get('attract_capture_timestamps',[])))>=3
        and (evidence.get('title_reference') or {}).get('matched') is True
        and bool((evidence.get('title_reference') or {}).get('sha256'))
        and (evidence.get('screen') or {}).get('phase')=='title')
    return terminal and (causal or visual or title)



def write_session(path, doc):
    temporary = path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(doc,indent=2)+"\n")
    temporary.replace(path)

def meditate_session(session_dir, games):
    """Never merge games. Analyze each episode separately, then summarize metadata."""
    from .learning_review import review_session
    results=[]
    for game in games:
        g=Path(game["path"])
        report=g/"report.json"
        if report.exists():
            run([sys.executable,"-m","experiments.ppal.evaluate_robotron_shadow",str(report)])
        # Deep replay meditation is valid only if THIS episode owns tracks.json.
        if (g/"tracks.json").exists():
            run([sys.executable,"-m","experiments.ppal.meditate_robotron",str(g)])
        results.append({
            "path":str(g),
            "report":str(report) if report.exists() else None,
            "shadow_evaluation":str(g/"shadow-evaluation.json")
                if (g/"shadow-evaluation.json").exists() else None,
            "predictive_meditation":str(g/"predictive-reconstruction.json")
                if (g/"predictive-reconstruction.json").exists() else None,
        })
    summary={
      "schema":"charlie-robotron-marathon-meditation-v1",
      "created_at":datetime.now(timezone.utc).isoformat(),
      "rule":"Independent episodes only; no trajectory/frame/track concatenation.",
      "games":results,
    }
    p=session_dir/"meditation.json"
    p.write_text(json.dumps(summary,indent=2)+"\n")
    review_session(session_dir, games)
    print(f"MEDITATION COMPLETE: {p}")

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--play-first',action='store_true',help='defer all expensive development until gameplay ends; requires developmental learning projects')
    ap.add_argument('--reflect-session',type=Path,help='resume offline reflection of an existing marathon; never arms camera/controller')
    ap.add_argument('--reflection-turns',type=int,default=12,help='bounded normal Executive turns after imports; durable work resumes later')
    ap.add_argument("--max-games",type=int)
    ap.add_argument("--game-seconds",type=float,default=None,
                    help="opt-in diagnostic duration, never normal game completion")
    ap.add_argument("--failed-starts",type=int,default=2)
    ap.add_argument("--retry-wait",type=float,default=5.0)
    ap.add_argument("--focus",type=float,default=1.30,
                    help="manual camera lens position passed to each game")
    ap.add_argument("--root",type=Path,default=Path("robotron-runs"))
    ap.add_argument("--arm",action="store_true",help="required to send controls")
    ap.add_argument('--processing-budget',type=float,default=300.,help='offline work budget; failure stops marathon and retains partial evidence')
    ap.add_argument('--developmental',action='store_true',help='automatic between-game evidence-backed experiments; 3..5 attempts')
    ap.add_argument('--seed-episode',type=Path,help='optional prior episode to process before developmental game 1')
    ap.add_argument('--learning-projects',action='store_true',help='opt-in durable diagnostic project continuity between developmental games')
    ap.add_argument('--ala-learning',action='store_true',help='opt-in bounded offline model investigations after completed episodes; requires learning projects')
    ap.add_argument('--learning-root',type=Path,help='durable experience artifacts and evidence; no live training')
    ap.add_argument('--ala-budget',type=float,default=60.,help='offline foundry budget 1..3600 seconds')
    ap.add_argument('--learned-semantics',type=Path,help='authorized frozen candidate manifest; physical readiness still checked by player')
    ap.add_argument('--ala-deployment-authority',type=Path,help='external bounded model deployment policy, never generated by learner')
    ap.add_argument('--project-evidence',type=Path,help='existing-format durable project evidence notebook; default beside local memory evaluator')
    a=ap.parse_args()
    if a.max_games is None:a.max_games=3 if a.developmental else 50
    import math
    if not 1 <= a.max_games <= 100: ap.error('--max-games must be 1..100')
    if a.game_seconds is not None and (not math.isfinite(a.game_seconds) or not 1 <= a.game_seconds <= 3600):
        ap.error('--game-seconds must be 1..3600')
    if not 1 <= a.failed_starts <= 10: ap.error('--failed-starts must be 1..10')
    if not math.isfinite(a.retry_wait) or not 0 <= a.retry_wait <= 60:
        ap.error('--retry-wait must be 0..60')
    if not math.isfinite(a.processing_budget) or not 10 <= a.processing_budget <= 3600:
        ap.error('--processing-budget must be 10..3600')
    if not 1<=a.reflection_turns<=1000:ap.error('--reflection-turns must be 1..1000')
    if not math.isfinite(a.ala_budget) or not 1<=a.ala_budget<=3600: ap.error('--ala-budget must be 1..3600')
    if a.reflect_session:
        if a.arm:ap.error('--reflect-session is offline; --arm is prohibited')
        result=reflect_marathon(a.reflect_session,a)
        print(json.dumps(result,indent=2))
        if result['phase']=='yielded':raise SystemExit(75)
        return
    if a.play_first and not (a.developmental and a.learning_projects):
        ap.error('--play-first requires --developmental --learning-projects')
    if not a.arm: ap.error("--arm is required for an autonomous marathon")
    if (a.learning_projects or a.project_evidence) and not a.developmental:
        ap.error('learning project options require --developmental')
    if (a.ala_learning or a.learning_root) and not a.learning_projects:
        ap.error('ALA options require --developmental --learning-projects')
    if a.project_evidence and not a.learning_projects:
        ap.error('--project-evidence requires --learning-projects')
    if a.developmental:
        if not 3<=a.max_games<=5:ap.error('developmental mode requires 3..5 bounded attempts')
        developmental_marathon(a)
        return
    if a.seed_episode:ap.error('--seed-episode requires --developmental')
    # Normal and developmental episodes share the same safe orchestration and
    # between-game pipeline. Normal mode leaves actuator bootstrap disabled.
    developmental_marathon(a)

if __name__=="__main__":
    main()
