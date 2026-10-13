"""Independent recording/boundary checks, committed to the existing journal.

Completion does not qualify an OCR score or establish learning improvement.
Original packages remain in place; records hold identities and hashes only.
"""
from pathlib import Path
import json
from memory.episode_identity import inspect_capture, validate_origin, artifact_manifest


def preserve_game(journal, game, *, marathon, returncode, report, on_progress=None, on_operation=None):
    from .marathon_robotron import established_gameplay, recording_readiness, safe_to_restart,qualified_game_over
    game = Path(game)
    report = report or {}
    def operation(name):
        if on_operation:on_operation(name)
    def completed(**detail):
        if on_progress:on_progress(detail)
    operation('capture_identity_verification')
    try:
        if not (game/'capture-origin.json').exists() and not (game/'report.json').exists():
            raise ValueError('no captured episode identity or report')
        identity = inspect_capture(game,on_progress=on_progress)
    except (OSError, ValueError, KeyError) as exc:
        identity = {'status':'unavailable', 'reason':str(exc)}
        # An interrupted seal must not erase the original occurrence identity.
        # These hashes remain diagnostic, never a qualified completion receipt.
        try:
            origin=json.loads((game/'capture-origin.json').read_text())
            validate_origin(origin)
            identity.update(capture_id=origin['capture_id'],provenance=origin.get('provenance'),
                            artifacts=artifact_manifest(game,on_progress=on_progress))
        except (OSError,ValueError,KeyError):pass
    try:
        report_matches=json.loads((game/'report.json').read_text())==report
    except (OSError,ValueError):report_matches=False
    operation('recording_verification')
    readiness = recording_readiness(game, report,on_progress=on_progress)
    invalid = bool(report.get('cal_recovery') or report.get('recording_error')
                   or report.get('failure_kind') in ('observation_failure','recording_failure'))
    playable = established_gameplay(report)
    operation('restart_boundary_validation')
    terminal = safe_to_restart(report, returncode, capture_root=game,on_progress=on_progress)
    classification = 'invalid' if invalid else 'completed' if playable and qualified_game_over(report,returncode) and readiness['status']=='ready' and report_matches else 'incomplete_unverified'
    capture_id = identity.get('capture_id') or identity.get('legacy_episode_id') or str(game.resolve())
    prior = [r for r in journal.records('game_completion')
             if r.data['episode'] == capture_id]
    content_id=identity.get('content_id')
    duplicate_content=bool(content_id and any(
        r.data['episode']!=capture_id and r.data['payload'].get('content_id')==content_id
        for r in journal.records('game_completion')))
    if duplicate_content and classification=='completed':classification='incomplete_unverified'
    payload = dict(schema='charlie-game-completion-v1', marathon=str(Path(marathon).resolve()),
        episode=str(game.resolve()), capture_id=capture_id, content_id=content_id,
        manifest_id=identity.get('manifest_id'),classification=classification,
        independence=dict(duplicate_content=duplicate_content,
            scope='distinct capture content and origin; not independent physical score qualification'),
        checks=dict(established_gameplay=playable, independently_supported_terminal=qualified_game_over(report,returncode),
                    report_matches_original=report_matches,
                    recording=readiness, confirmed_invalidator=invalid),
        provenance=report.get('provenance'), artifacts=identity.get('artifacts',{}),
        controls='session-evidence.sqlite3', agency='agency.jsonl',
        timing=report.get('session_timing'), start=report.get('start_decision'),
        terminal=report.get('episode_end'), camera=report.get('sensory_preflight'),
        score=report.get('score_summary') or dict(status='unmeasured',self_score=None),
        score_qualification='not independently verified; excluded from capability improvement claims',
        experiment=report.get('experiment_status'),
        notebook_reference=str((Path(marathon)/'experiment-evidence.sqlite3').resolve()),
        project_context_reference=str((Path(marathon)/'session.json').resolve()),
        invalidation=report.get('cal_recovery'),
        returncode=returncode)
    if prior:
        if prior[-1].data['payload'] != payload:
            raise ValueError('conflicting finalized game evidence; preserve original record')
        completed(operation='game_completion_idempotence_verified',record_id=prior[-1].id)
        return dict(record_id=prior[-1].id, classification=classification, duplicate=True)
    operation('game_completion_journal_commit')
    record = journal.append('game_completion', payload, episode=capture_id,
        producer='independent-recording-boundary-validator',version='1')
    completed(operation='game_completion_committed',record_id=record.id)
    return dict(record_id=record.id, classification=classification, duplicate=False)
