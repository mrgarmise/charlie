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


def run_bounded(cmd, timeout):
    print('+', ' '.join(map(str,cmd)),flush=True)
    try:
        return subprocess.run(cmd,check=False,timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        # subprocess.run kills/reaps its child. TCP disconnect releases controls
        # in the existing Zero transport; no next START after a timeout.
        print('DEVELOPMENT STOP: child exceeded wall-time bound',flush=True)
        return 124


def process_completed_episode(game, output, gateway, commitments, plan=None, executive=None):
    """Existing E/E + Reflection + Meditation + Evaluator, between games only."""
    from memory.evidence import EvidenceJournal
    from .episode_evidence import import_episode, derive_episode, summarize
    from .reflect_robotron import reflect_evidence, reflect_actuator_evidence, reflect_learning_projects
    from .experiment_return import resolve_experiment
    from .meditate_robotron import meditate, quality
    from .evaluate_robotron_shadow import evaluate
    output.mkdir(parents=True,exist_ok=True)
    journal=EvidenceJournal(output/'evidence.sqlite3')
    try:
        episode=import_episode(game,journal)
        # Resolve live commitment first. Replay diagnostics must not masquerade
        # as outcomes of the pre-game experiment.
        resolution=resolve_experiment(game,journal,episode,commitments,plan,gateway) if plan else None
        derive_episode(game,journal,episode)
        reflection=reflect_evidence(journal,episode,gateway)
        proposals=reflect_actuator_evidence(game,journal,episode,gateway)
        project_updates = None
        if executive is not None:
            project_proposals = reflect_learning_projects(journal, episode, proposals)
            ids = [executive.propose(p['proposal'], journal, [p['evidence_id']]) for p in project_proposals]
            assessment = None
            if plan and plan.get('project_id') and resolution:
                assessment = executive.record_result(plan['project_id'], plan, resolution, commitments, episode=episode)
            project_updates = dict(proposed=ids, assessment=assessment)
        report=load_report(game/'report.json')
        (output/'shadow-evaluation.json').write_text(json.dumps(evaluate(report),indent=2)+'\n')
        meditation=None
        if (game/'tracks.json').exists():
            tracks=json.loads((game/'tracks.json').read_text()).get('tracks',[])
            rebuilt,history,merges=meditate(tracks)
            meditation={'source':str(game/'tracks.json'),'history':history,'merges':merges,
                        'quality':quality(rebuilt),'note':'offline interpreted IDs; not canonical identity or policy advice'}
            (output/'meditation.json').write_text(json.dumps(meditation,indent=2)+'\n')
        result={'episode':episode,'resolution':resolution,'reflection':reflection,
                'proposals':proposals,'meditation':str(output/'meditation.json') if meditation else None,
                'evidence':summarize(journal,episode)}
        if executive is not None:
            result['learning_projects'] = project_updates
        (output/'between-game.json').write_text(json.dumps(result,indent=2)+'\n')
        return result
    finally:
        journal.close()


def developmental_marathon(args, *, driver=run_bounded, gateway=None):
    """Bounded runner with optional project continuity, between games only."""
    from collections import Counter
    from memory.evidence import EvidenceJournal
    from memory.gateway import MemoryGateway
    from .experiment_return import select_experiment
    gateway=gateway or MemoryGateway()
    session=args.root/f'development-{stamp()}'
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
    try:
        if args.seed_episode:
            doc['seed_processing']=process_completed_episode(args.seed_episode,session/'seed-evidence',gateway,commitments,executive=executive)
        for index in range(1,args.max_games+1):
            game=session/f'game-{index:02d}'
            selection = None
            context = None
            if executive:
                selection = executive.select(methods={'actuator-response'},
                    resources={'camera-evidence', 'actuator-experiment-slot'}, authorized_methods={'actuator-response'})
                if selection['project']:
                    context = executive.chooser_context(selection['project']['id'])
            plan = None if executive and context is None else select_experiment(
                gateway,commitments,game,horizon_seconds=args.game_seconds+120.,project_context=context)
            plan_path=session/f'game-{index:02d}-experiment.json'
            if plan:write_session(plan_path,plan)
            reason=plan['reason'] if plan else 'no justified experiment yet; existing policy only'
            print(f'DEVELOPMENT GAME {index}/{args.max_games}: {reason}',flush=True)
            write_session(session/'session.json',doc)
            cmd=[sys.executable,'-m','experiments.ppal.play_robotron','--arm','--bootstrap-body-fire',
                 '--seconds',str(args.game_seconds),'--focus',str(args.focus),'--recalibrate','--output',str(game)]
            if plan:cmd.extend(['--experiment-plan',str(plan_path)])
            if executive:
                viewer_context = session/f'game-{index:02d}-observer-context.json'
                write_session(viewer_context, {'episode':str(game.resolve()), 'project':selection['project']})
                cmd.extend(['--observer-context', str(viewer_context)])
            rc=driver(cmd,args.game_seconds+120.)
            report=load_report(game/'report.json')
            entry={'path':str(game),'returncode':rc,'result':report.get('result') if report else 'missing report',
                   'experiment':plan,'reason_for_experiment':reason}
            if executive:
                entry['project_selection'] = selection
            doc['games'].append(entry)
            write_session(session/'session.json',doc)
            if report:
                entry['score_evidence']=report.get('score_summary',{'self_score':report.get('score'),'status':report.get('score_status','unknown')})
                entry['score_attribution']='unknown; accepted reading is not independently verified score'
                entry['self_status']=dict(Counter(s.get('identity_status','unknown') for s in report.get('steps',[])))
                entry['between_game']=process_completed_episode(game,session/f'game-{index:02d}-evidence',gateway,commitments,plan,executive)
            else:
                entry['between_game']={'status':'unknown; no complete report'}
                if plan:
                    resolution=commitments.resolve(plan['prediction_id'],sources=(),result='unresolved',reason='child ended without report')
                    entry['resolution_id']=resolution.id
                    if executive and plan.get('project_id'):
                        executive.record_result(plan['project_id'], plan,
                            dict(resolution_id=resolution.id, result='unresolved', reason='child ended without report'),
                            commitments, episode='missing-report:'+str(game))
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
    ap.add_argument("--game-seconds",type=float,default=60.0,
                    help="safety horizon per current single-game runner")
    ap.add_argument("--failed-starts",type=int,default=2)
    ap.add_argument("--retry-wait",type=float,default=5.0)
    ap.add_argument("--focus",type=float,default=1.30,
                    help="manual camera lens position passed to each game")
    ap.add_argument("--root",type=Path,default=Path("robotron-runs"))
    ap.add_argument("--arm",action="store_true",help="required to send controls")
    ap.add_argument('--developmental',action='store_true',help='automatic between-game evidence-backed experiments; 3..5 attempts')
    ap.add_argument('--seed-episode',type=Path,help='optional prior episode to process before developmental game 1')
    ap.add_argument('--learning-projects',action='store_true',help='opt-in durable diagnostic project continuity between developmental games')
    ap.add_argument('--project-evidence',type=Path,help='existing-format durable project evidence notebook; default beside local memory evaluator')
    a=ap.parse_args()
    if a.max_games is None:a.max_games=3 if a.developmental else 50
    import math
    if not 1 <= a.max_games <= 100: ap.error('--max-games must be 1..100')
    if not math.isfinite(a.game_seconds) or not 1 <= a.game_seconds <= 3600:
        ap.error('--game-seconds must be 1..3600')
    if not 1 <= a.failed_starts <= 10: ap.error('--failed-starts must be 1..10')
    if not math.isfinite(a.retry_wait) or not 0 <= a.retry_wait <= 60:
        ap.error('--retry-wait must be 0..60')
    if not a.arm: ap.error("--arm is required for an autonomous marathon")
    if (a.learning_projects or a.project_evidence) and not a.developmental:
        ap.error('learning project options require --developmental')
    if a.project_evidence and not a.learning_projects:
        ap.error('--project-evidence requires --learning-projects')
    if a.developmental:
        if not 3<=a.max_games<=5:ap.error('developmental mode requires 3..5 bounded attempts')
        if not 1<=a.game_seconds<=120:ap.error('developmental game seconds must be 1..120')
        developmental_marathon(a)
        return
    if a.seed_episode:ap.error('--seed-episode requires --developmental')
    session=a.root/f"marathon-{stamp()}"
    session.mkdir(parents=True,exist_ok=False)
    doc={"schema":SCHEMA,"started_at":datetime.now(timezone.utc).isoformat(),
         "status":"running","rule":"games remain independent","games":[],"failed_starts":[]}
    write_session(session/"session.json",doc)

    failures=0
    try:
        while len(doc["games"]) < a.max_games:
            game=a.root/f"play-{stamp()}"
            # Avoid same-second collision without ever reusing an episode directory.
            while game.exists():
                time.sleep(1.05); game=a.root/f"play-{stamp()}"
            rc=run([sys.executable,"-m","experiments.ppal.play_robotron",
                    "--arm","--seconds",str(a.game_seconds),
                    "--focus",str(a.focus),"--output",str(game)])
            report=load_report(game/"report.json")
            if established_gameplay(report):
                failures=0
                entry={"path":str(game),"returncode":rc,
                       "result":report.get("result"),"ticks":report.get("ticks"),
                       "score":None,"score_status":"pending"}
                doc["games"].append(entry)
                run([sys.executable,"-m","experiments.ppal.evaluate_robotron_shadow",
                     str(game/"report.json")])
                write_session(session/"session.json",doc)
                # Current player has a safety horizon. If it timed out while gameplay
                # was active, do NOT press START: that could spend a credit mid-game.
                if report.get("result")=="TIME LIMIT":
                    print("GAMEPLAY HIT SAFETY HORIZON; stopping marathon rather than risking START mid-game.")
                    doc["status"]="safety_horizon"
                    break
                if not safe_to_restart(report, rc):
                    doc['status'] = 'needs_episode_end_review'
                    print('STOP: tracking loss is not confirmed game over; no further START.')
                    break
                print("Confirmed game over; preparing next START.")
                time.sleep(a.retry_wait)
                continue

            failures += 1
            doc["failed_starts"].append({"path":str(game),"returncode":rc,
                                         "at":datetime.now(timezone.utc).isoformat()})
            write_session(session/"session.json",doc)
            print(f"NO GAMEPLAY after START attempt {failures}/{a.failed_starts}")
            if not safe_to_restart(report, rc):
                doc['status'] = 'unverified_start_or_episode_end'
                break
            if failures >= a.failed_starts:
                doc["status"]="credits_exhausted_or_gameplay_unavailable"
                break
            time.sleep(a.retry_wait)
    except KeyboardInterrupt:
        doc["status"]="interrupted"
    finally:
        if doc["status"]=="running": doc["status"]="max_games_reached"
        doc["ended_at"]=datetime.now(timezone.utc).isoformat()
        write_session(session/"session.json",doc)
        print(f"MARATHON ENDED: {doc['status']}; games={len(doc['games'])}")
        print("ENTERING MEDITATION")
        meditate_session(session,doc["games"]+doc["failed_starts"])

if __name__=="__main__":
    main()
