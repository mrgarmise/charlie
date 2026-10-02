"""Post-game Robotron reflection using Charlie's existing durable memory system.

Consumes one replay directory, compares the episode with prior locally evaluated
Charlie memories (and MARM recall when available), forms selected experiences,
and writes a small question queue for uncertainties worth human review.

This is analysis only: it imports no controller and never changes live policy.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from memory.former import Experience
from memory.gateway import MemoryGateway
from memory.marm import MarmWriteError

DEFAULT_QUESTIONS = Path.home() / ".local/share/charlie/robotron-questions.jsonl"
ACTUATOR_HYPOTHESIS_MARKER = 'Actuator response hypothesis: '


def reflect_actuator_evidence(root, journal, episode, gateway):
    """Generate/rank one-actuator variations using observed response distributions.

    Directions, settings and expected verdicts are data, never selected constants.
    Existing Experience/Evaluator remain the hypothesis and ranking machinery.
    """
    from memory.evidence import canonical, ArtifactReader, digest
    read_verified = ArtifactReader(root)
    from .hands import AXES
    from collections import Counter
    groups = {}
    fire_counts = Counter()
    fire_sources = {}
    executions = set()
    observations = {}
    for record in journal.records('observation'):
        if record.data['episode'] != episode or record.data['payload'].get('category') != 'agency_tracking_observation':
            continue
        row = read_verified(record.data['payload']['artifact'])
        control = row.get('control_execution') or {}
        fire = control.get('fire')
        if control and fire in AXES and fire != 'STAY' and digest(control) not in executions:
            executions.add(digest(control))
            fire_counts[fire] += 1
            fire_sources.setdefault(fire,[]).append(record.id)
        window = row.get('response_window') or {}
        origin = observations.get(window.get('origin_at'),row)
        identity = origin.get('identity_status', 'confirmed' if origin.get('self_track_id') is not None else 'unknown')
        candidate = origin.get('controlled_track_id',origin.get('self_track_id'))
        observations[row.get('capture_timestamp')] = row
        if identity not in ('provisional','confirmed') or candidate is None or window.get('endpoint') != 2 or row.get('global_motion'):
            continue
        body = control.get('move')
        if body not in AXES or body=='NONE' or fire not in AXES or fire=='STAY':
            continue
        evidence = next((x for x in row.get('evidence',[]) if x.get('track_id')==candidate),None)
        if not evidence or not isinstance(evidence.get('reason'),str):
            continue
        if any(e.get('track_id')==candidate and e.get('kind') in ('ambiguous','created') for e in row.get('tracking',{}).get('events',[])):
            continue
        groups.setdefault((candidate,body),{}).setdefault(control.get('started_at'),
            dict(record=record,fire=fire,result=evidence['reason'],identity=identity,sample=row.get('sample')))
    proposals=[]
    # This is a bounded local one-variable proposal adapter, not broad curiosity.
    for (candidate,body), windows in sorted(groups.items()):
        rows=list(windows.values())
        fires=sorted({r['fire'] for r in rows})
        distribution=Counter(r['result'] for r in rows)
        ranked_results=distribution.most_common()
        if len(rows)<2 or len(fires)<2 or (len(ranked_results)>1 and ranked_results[0][1]==ranked_results[1][1]):
            continue
        expected,support=ranked_results[0]
        for alternate in sorted(set(AXES)-{'STAY'}):
            joint=[r for r in rows if r['fire']==alternate]
            untested=not joint
            spec=dict(schema='charlie-actuator-test-v2',body=body,fire=alternate,
                      expected=expected,variable_changed='one FIRE setting; observed BODY setting held fixed',
                      observed_result_distribution=dict(distribution),
                      source_episode=episode,source_track_id=candidate,
                      source_evidence=[r['record'].id for r in rows],source_fire_settings=fires,
                      source_samples=[r['sample'] for r in rows],
                      setting_frequency=fire_counts[alternate],setting_evidence=fire_sources.get(alternate,[]),
                      evidence_windows=len(rows),joint_observations=len(joint),
                      proposal_rank=[int(untested),support/len(rows),len(rows),fire_counts[alternate]],
                      hypothesis_status='tentative; SELF unverified',score_claim=None,
                      confidence_note='heuristic hypothesis score, not calibrated probability')
            derived=journal.append('event',dict(category='actuator_response_hypothesis_proposal',proposal=spec),
                episode=episode,sources=tuple(dict.fromkeys(spec['source_evidence']+spec['setting_evidence'])),
                producer='Reflection',version='actuator-response-v2')
            event=Experience(kind='observation',summary=ACTUATOR_HYPOTHESIS_MARKER+canonical(spec),
                source='ppal:actuator-response-reflection',subject='actuator response',
                confidence=.5,significant=True,novelty=untested,
                tags=('actuator-hypothesis','diagnostic','tentative',f'body:{body}',f'fire:{alternate}'),evidence=derived.id)
            gateway.remember(event)
            proposals.append(dict(proposal=spec,evidence_id=derived.id))
    return proposals


def reflect_learning_projects(journal, episode, proposals):
    """Normalize existing hypotheses for generic project Reflection, not strategy."""
    from memory.learning_projects import reflect_project_opportunities
    from .hands import AXES
    hypotheses = []
    for row in proposals:
        spec = row['proposal']
        hypotheses.append(dict(method='actuator-response', scope={'body': spec['body']},
            established_objective='official_game_score',
            expected=spec['expected'], evidence_ids=[row['evidence_id']],
            conditions=[{'fire': f} for f in sorted(set(AXES)-{'STAY'})],
            observed_conditions=[{'fire': f} for f in spec['source_fire_settings']],
            requires=['camera-evidence', 'actuator-experiment-slot']))
    return reflect_project_opportunities(journal, episode, hypotheses)


def reflect_evidence(journal, episode, gateway):
    """Consolidate explicit diagnostic resolutions through the existing path.

    No automatic helpful/harmful credit, semantic teaching or policy update.
    Each model version retains its own evidence identity in MemoryEvaluator.
    """
    from collections import Counter
    rows = [r for r in journal.records('resolution_reference') if r.data['episode'] == episode]
    versions = sorted({r.data['version'] for r in rows})
    findings = []
    for version in versions:
        selected = [r for r in rows if r.data['version'] == version]
        counts = Counter(r.data['payload']['result'] for r in selected)
        event = Experience(kind='observation', source='ppal:evidence-reflection',
            summary=f"Replay model {version}: {dict(counts)}. These are diagnostic replay tests, not live commitments or causal game rules",
            subject=episode, confidence=1.0, significant=True,
            tags=('ppal','reflection','prediction-diagnostic'),
            evidence=f"{journal.path.resolve()}#" + selected[-1].id)
        promoted = gateway.remember(event)
        findings.append(dict(version=version,results=dict(counts),promoted=promoted,
                             evidence_ids=[r.id for r in selected]))
    return dict(episode=episode,findings=findings,policy_updated=False,
                memory_path='Experience -> MemoryGateway -> MemoryEvaluator -> existing store/MARM outbox')


def _load(path):
    return json.loads(Path(path).read_text())


def _percent(n, d):
    return 0.0 if not d else 100.0 * n / d


def analyze(summary, rows, tracks):
    """Derive conservative episode observations; do not infer game outcomes."""
    frames = int(summary.get("frames", 0))
    decisions = int(summary.get("decision_frames", 0))
    unknown = int(summary.get("self_unknown_frames", 0))
    reacq = int(summary.get("self_reacquisitions", 0))
    action_counts = {
        (a.get("move"), a.get("fire")): int(a.get("count", 0))
        for a in summary.get("actions", [])
    }
    stay_none = action_counts.get(("STAY", "NONE"), 0)

    target_frames = sum(bool(r.get("targets")) for r in rows if r.get("status") == "decision")
    threat_frames = sum(bool(r.get("threats")) for r in rows if r.get("status") == "decision")

    observations = {
        "frames": frames,
        "decisions": decisions,
        "self_unknown_frames": unknown,
        "self_unknown_pct": round(_percent(unknown, frames), 1),
        "self_reacquisitions": reacq,
        "stay_none_frames": stay_none,
        "stay_none_pct_of_decisions": round(_percent(stay_none, decisions), 1),
        "target_frames": target_frames,
        "target_pct_of_decisions": round(_percent(target_frames, decisions), 1),
        "threat_frames": threat_frames,
        "threat_pct_of_decisions": round(_percent(threat_frames, decisions), 1),
        "visual_tracks": len(tracks),
    }

    # Reliability is about the replay interpretation, not about success in the game.
    # A replay with unstable SELF or an implausibly fragmented visual field should
    # diagnose perception before drawing strategy conclusions.
    tracks_per_frame = 0.0 if not frames else len(tracks) / frames
    observations["tracks_per_frame"] = round(tracks_per_frame, 2)
    reliability_reasons = []
    if observations["self_unknown_pct"] >= 15:
        reliability_reasons.append("SELF unknown on >=15% of frames")
    if reacq >= 3:
        reliability_reasons.append("SELF reacquired >=3 times")
    if tracks_per_frame >= 3:
        reliability_reasons.append("visual tracking is highly fragmented")
    if decisions and target_frames == 0 and threat_frames == decisions:
        reliability_reasons.append("semantic coverage is all-threat/no-target")
    observations["replay_reliable_for_strategy"] = not reliability_reasons
    observations["reliability_reasons"] = reliability_reasons

    findings = []
    if unknown:
        findings.append(("self_uncertainty",
                         f"SELF was unknown for {unknown}/{frames} frames "
                         f"({observations['self_unknown_pct']:.1f}%)."))
    if reacq:
        findings.append(("self_reacquisition",
                         f"SELF required {reacq} replay reacquisitions."))
    if decisions and stay_none:
        findings.append(("inaction",
                         f"Charlie chose STAY/NONE on {stay_none}/{decisions} decision frames "
                         f"({observations['stay_none_pct_of_decisions']:.1f}%)."))
    if decisions:
        findings.append(("perception_coverage",
                         f"Targets appeared on {target_frames}/{decisions} decision frames and "
                         f"threats on {threat_frames}/{decisions}."))
    if reliability_reasons:
        findings.append(("replay_quality",
                         "Replay is not yet reliable for strategy conclusions: "
                         + "; ".join(reliability_reasons) + "."))
    return observations, findings


def _prior_local(gateway, limit=30):
    return gateway.evaluator.recent(limit=limit)


def _prior_remote(gateway, query):
    try:
        return gateway.recall(query, limit=10)
    except MarmWriteError:
        return []


def _occurrences(prior, phrase):
    needle = phrase.lower()
    return sum(needle in item.get("text", "").lower() for item in prior)


def _queue_question(path, question):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                existing.add(json.loads(line).get("id"))
            except (ValueError, TypeError):
                pass
    if question["id"] in existing:
        return False
    with path.open("a") as stream:
        stream.write(json.dumps(question, ensure_ascii=False) + "\n")
    return True


def reflect(replay_dir, gateway=None, questions_path=DEFAULT_QUESTIONS):
    replay_dir = Path(replay_dir)
    summary = _load(replay_dir / "summary.json")
    rows = _load(replay_dir / "replay.json")
    track_doc = _load(replay_dir / "tracks.json")
    tracks = track_doc.get("tracks", [])

    gateway = gateway or MemoryGateway()
    prior = _prior_local(gateway)
    remote = _prior_remote(
        gateway,
        "Robotron replay self tracking reacquisition perception decisions inaction")
    observations, findings = analyze(summary, rows, tracks)

    recording = str(summary.get("recording") or replay_dir)
    episode_key = recording.replace("/", "_")
    source = "ppal:robotron-reflection"

    promoted = []
    for category, text in findings:
        prior_count = _occurrences(prior, category.replace("_", " "))
        recurring = prior_count > 0
        event = Experience(
            kind="observation",
            summary=text,
            source=source,
            subject=category,
            confidence=1.0,
            novelty=not recurring,
            significant=(recurring
                         or category in ("self_uncertainty", "replay_quality")
                         or (category == "inaction"
                             and observations["replay_reliable_for_strategy"])),
            tags=("robotron", "reflection", category,
                  "diagnostic" if not observations["replay_reliable_for_strategy"]
                  else "strategy-capable"),
            evidence=f"robotron:{episode_key}:{category}",
        )
        if gateway.remember(event):
            promoted.append(category)

    questions = []
    # Questions are deliberately about interpretation/teaching, not facts the
    # replay can settle by counting its own evidence.
    if (observations["stay_none_pct_of_decisions"] >= 50
            and observations["replay_reliable_for_strategy"]):
        qid = f"robotron:{episode_key}:inaction-meaning"
        questions.append({
            "id": qid,
            "status": "open",
            "category": "strategy",
            "recording": recording,
            "question": (
                f"I chose STAY/NONE on {observations['stay_none_frames']}/"
                f"{observations['decisions']} decision frames "
                f"({observations['stay_none_pct_of_decisions']:.1f}%). "
                "My replay passed its perception-quality checks. When we review "
                "representative frames, were these appropriate wait decisions?"
            ),
            "evidence": str(replay_dir / "replay.json"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    if observations["self_unknown_pct"] >= 15 or observations["self_reacquisitions"] >= 3:
        qid = f"robotron:{episode_key}:self-identity"
        questions.append({
            "id": qid,
            "status": "open",
            "category": "perception",
            "recording": recording,
            "question": (
                f"I lacked SELF for {observations['self_unknown_frames']} frames and "
                f"reacquired it {observations['self_reacquisitions']} times. "
                "I should first inspect those moments offline; if ambiguity remains, "
                "I may need you to identify which sprite is me."
            ),
            "evidence": str(replay_dir / "tracks.json"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    queued = sum(_queue_question(questions_path, q) for q in questions)

    result = {
        "schema": "charlie-robotron-reflection-v2",
        "recording": recording,
        "replay": str(replay_dir),
        "observations": observations,
        "findings": [{"category": c, "summary": t} for c, t in findings],
        "comparison": {
            "local_memories_considered": len(prior),
            "remote_memories_recalled": len(remote),
            "note": ("MARM recall is optional; local evaluator history remains usable "
                     "when MARM is unavailable."),
        },
        "memory": {"promoted_categories": promoted},
        "questions": questions,
        "new_questions_queued": queued,
    }
    (replay_dir / "reflection.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay_dir", type=Path)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    args = parser.parse_args()

    result = reflect(args.replay_dir, questions_path=args.questions)
    o = result["observations"]
    print(f"REFLECTION: {result['recording']}")
    print(f"SELF UNKNOWN: {o['self_unknown_frames']}/{o['frames']} "
          f"({o['self_unknown_pct']:.1f}%)")
    print(f"SELF REACQUISITIONS: {o['self_reacquisitions']}")
    print(f"STAY/NONE: {o['stay_none_frames']}/{o['decisions']} decisions "
          f"({o['stay_none_pct_of_decisions']:.1f}%)")
    print("STRATEGY RELIABILITY: "
          + ("PASS" if o["replay_reliable_for_strategy"] else "DEFER"))
    if o["reliability_reasons"]:
        print("WHY: " + "; ".join(o["reliability_reasons"]))
    print(f"PRIOR LOCAL MEMORIES: {result['comparison']['local_memories_considered']}")
    print(f"REMOTE RECALLS: {result['comparison']['remote_memories_recalled']}")
    print(f"MEMORIES PROMOTED: {len(result['memory']['promoted_categories'])}")
    print(f"NEW QUESTIONS: {result['new_questions_queued']}")
    print(f"Reflection: {args.replay_dir / 'reflection.json'}")
    print(f"Question queue: {args.questions.expanduser()}")


if __name__ == "__main__":
    main()


def reflect_episode_context(root,journal,episode,gateway,*,plan=None,resolution=None,meditation=None):
    """Connect evidence gaps to existing Reflection, memory and question queue.

    These are interpretation questions, not tactical proposals or selected goals.
    Replay records remain correlated observations of one source episode.
    """
    from memory.evidence import ArtifactReader,digest
    read=ArtifactReader(root);sources=[];identities=Counter();report={};external=[]
    for record in journal.records('observation'):
        if record.data['episode']!=episode:continue
        category=record.data['payload'].get('category')
        if category not in ('session_report','agency_tracking_observation','external_observation'):continue
        row=read(record.data['payload']['artifact']);sources.append(record.id)
        if category=='session_report':report=row
        elif category=='external_observation':external.append(row)
        else:identities[row.get('identity_status','unknown')]+=1
    questions=[]
    if identities.get('unknown'):questions.append(dict(category='self_uncertainty',question='Which observations distinguish loss of identity from loss of the physical object?',measured=dict(unknown_samples=identities['unknown'],samples=sum(identities.values()))))
    if (report.get('episode_end') or {}).get('confirmed') is not True:questions.append(dict(category='episode_boundary',question='Which missing independent observations could settle the episode boundary?',measured=dict(result=report.get('result'),boundary='unverified')))
    if meditation and meditation.get('merges'):questions.append(dict(category='retrospective_identity',question='Which additional observations could verify or contradict the reconstructed identity links?',measured=dict(hypothesized_links=len(meditation['merges']),independently_verified_links=None)))
    score=[dict(source='automated_tracker_report',value=(report.get('score_summary') or {}).get('self_score',report.get('score')),verified=False),*external]
    if external:questions.append(dict(category='observation_agreement',question='What explains disagreement between these separately preserved observations?',measured=dict(observations=score)))
    context=dict(category='postgame_learning_context',independent_source_episodes=1,objective='official_game_score',prediction=plan,resolution=resolution,identity_samples=dict(identities),score_observations=score,causal_performance_change='unknown; no controlled comparison',questions=questions,meditation_provenance={k:meditation.get(k) for k in ('source_sha256','version')} if meditation else None,meditation_status='retrospective hypotheses, not verified physical identity' if meditation else 'unavailable')
    event=journal.append('event',context,episode=episode,sources=tuple(sources),producer='Reflection',version='episode-context-v1')
    for question in questions:_queue_question(gateway.evaluator.path.with_name('robotron-questions.jsonl'),dict(question,id=digest(dict(episode=episode,question=question)),status='open',recording=str(root),evidence=event.id,episode=episode))
    gateway.remember(Experience(kind='observation',summary=f"One source episode: identity reports {dict(identities)}; outcome {report.get('result')}; experiment {(resolution or {}).get('result','none')}; {len(questions)} unresolved evidence questions. Retrospective links and score changes do not establish causal performance improvement",source='ppal:episode-context-reflection',subject=episode,confidence=1.,significant=True,tags=('reflection','diagnostic','uncertain'),evidence=event.id))
    return dict(context,evidence_id=event.id)
