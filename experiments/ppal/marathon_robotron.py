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


def process_supervised(game, output, gateway, commitments, plan=None, executive=None, budget=300., chunks=3):
    from .progress_supervision import supervise
    output.mkdir(parents=True, exist_ok=True)
    config = dict(game=str(game), output=str(output), evaluator=str(gateway.evaluator.path),
                  outbox=str(gateway.store.path), project=gateway.project, session=gateway.session,
                  commitments=str(commitments.path), plan=plan,
                  project_evidence=str(executive.journal.path) if executive else None,
                  progress=str(output/'processing-progress.json'), work_budget=budget)
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


def process_completed_episode(game, output, gateway, commitments, plan=None, executive=None, progress=None, work_budget=None):
    """Existing E/E + Reflection + Meditation + Evaluator, between games only."""
    from memory.evidence import EvidenceJournal
    from .episode_evidence import import_episode, derive_episode, summarize
    from .reflect_robotron import reflect_evidence, reflect_actuator_evidence, reflect_learning_projects
    from .experiment_return import resolve_experiment
    from .meditate_robotron import meditate, quality
    from .evaluate_robotron_shadow import evaluate
    output.mkdir(parents=True,exist_ok=True)
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
        print(f'BETWEEN GAME: {name}', flush=True)
    journal=EvidenceJournal(output/'evidence.sqlite3', on_progress=pulse)
    try:
        stage('import')
        episode=import_episode(game,journal)
        # Resolve live commitment first. Replay diagnostics must not masquerade
        # as outcomes of the pre-game experiment.
        stage('resolve_experiment')
        resolution=resolve_experiment(game,journal,episode,commitments,plan,gateway) if plan else None
        assessment = None
        if executive is not None and plan and plan.get('project_id') and resolution:
            assessment=executive.record_result(plan['project_id'],plan,resolution,commitments,episode=episode)
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
        if (game/'tracks.json').exists():
            tracks=json.loads((game/'tracks.json').read_text()).get('tracks',[])
            rebuilt,history,merges=meditate(tracks,on_progress=pulse)
            meditation={'source':str(game/'tracks.json'),'history':history,'merges':merges,
                        'quality':quality(rebuilt),'note':'offline interpreted IDs; not canonical identity or policy advice'}
            (output/'meditation.json').write_text(json.dumps(meditation,indent=2)+'\n')
        result={'episode':episode,'resolution':resolution,'reflection':reflection,
                'proposals':proposals,'meditation':str(output/'meditation.json') if meditation else None,
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
    plan=None
    # Tests may inject an in-process driver and gateway. Physical default always
    # supervises offline work in a separate process with existing durable stores.
    if driver is run_bounded:
        def processor(*values, **options):
            return process_supervised(*values, **options, budget=getattr(args,'processing_budget',300.))
    else:
        processor = process_completed_episode
    try:
        if args.seed_episode:
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
            if executive:
                viewer_context = session/f'game-{index:02d}-observer-context.json'
                write_session(viewer_context, {'episode':str(game.resolve()), 'project':selection['project']})
                cmd.extend(['--observer-context', str(viewer_context)])
            rc=driver(cmd,30.)
            report=load_report(game/'report.json')
            entry={'path':str(game),'returncode':rc,'result':report.get('result') if report else 'missing report',
                   'experiment':plan,'reason_for_experiment':reason,
                   'supervision':load_report(game.parent/(game.name+'-progress-supervisor.json'))}
            if executive:
                entry['project_selection'] = selection
            doc['games'].append(entry)
            write_session(session/'session.json',doc)
            if report:
                entry['score_evidence']=report.get('score_summary',{'self_score':report.get('score'),'status':report.get('score_status','unknown')})
                entry['score_attribution']='unknown; accepted reading is not independently verified score'
                entry['self_status']=dict(Counter(s.get('identity_status','unknown') for s in report.get('steps',[])))
                entry['between_game']=processor(game,session/f'game-{index:02d}-evidence',gateway,commitments,plan,executive)
            else:
                entry['between_game']={'status':'unknown; no complete report'}
                if plan:
                    resolution=commitments.resolve(plan['prediction_id'],sources=(),result='unresolved',reason='child ended without report')
                    entry['resolution_id']=resolution.id
                    if executive and plan.get('project_id'):
                        executive.record_result(plan['project_id'], plan,
                            dict(resolution_id=resolution.id, result='unresolved', reason='child ended without report'),
                            commitments, episode='missing-report:'+str(game))
                if game.exists():
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
                doc['status']='bounded_attempts_complete';break
            if not safe_to_restart(report,rc):
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
        if plan and not any(r.data['payload']['prediction_id']==plan['prediction_id'] for r in commitments.records('resolution')):
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
    return doc

def load_report(path):
    try: return json.loads(path.read_text())
    except (OSError, ValueError): return None

def established_gameplay(report):
    """Conservative: the existing player must actually have produced game steps."""
    if not report: return False
    steps=report.get("steps") or []
    return bool(report.get("armed") and report.get("acquisition") and
                any("action" in s for s in steps))

def safe_to_restart(report, returncode=0):
    """Only an explicit, evidenced terminal screen may authorize another START."""
    if returncode != 0 or not report:
        return False
    end = report.get('episode_end', {})
    evidence = end.get('evidence') or {}
    return (report.get('result') == 'GAME OVER' and end.get('state') == 'game_over'
            and end.get('confirmed') is True and isinstance(evidence, dict)
            and evidence.get('rule') == 'persistent_not_gameplay_plus_no_controlled_self'
            and evidence.get('not_gameplay_streak', 0) >= 8
            and evidence.get('agency_failures', 0) >= 1
            and (evidence.get('screen') or {}).get('state') == 'not_gameplay'
            and (evidence.get('screen') or {}).get('phase') in ('startable','terminal'))


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
    if not a.arm: ap.error("--arm is required for an autonomous marathon")
    if (a.learning_projects or a.project_evidence) and not a.developmental:
        ap.error('learning project options require --developmental')
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
