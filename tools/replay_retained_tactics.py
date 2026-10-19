"""Offline fixed-input Hindbrain controls from preserved tactical predictions.

No camera or controller imports. The ledger is read-only and never activated.
Run again in a fresh process to compare reload results. Source worlds are
historical PPAL interpretations, not independently qualified object identities.
"""
import argparse
from dataclasses import asdict
import json
import hashlib
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.ppal.hindbrain import Hindbrain
from experiments.ppal.models import Goal, Object, Position, WorldState
from experiments.ppal.tactical_memory import TacticalDiagnosticMemory
from memory.evidence import digest


def predictions(path, identifiers):
    """Immutable byte-checked view; validate exact prediction content IDs.

    Source journals undergo full graph verification in the recovery command.
    This replay validates the referenced subset without repeating graph walks.
    """
    path = Path(path).resolve(strict=True)
    if any(Path(str(path) + s).exists() for s in ('-wal', '-shm', '-journal')):
        raise ValueError('quiesced journal snapshot required')
    def checksum():
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    before = checksum()
    connection = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        for identifier in sorted(identifiers):
            result = connection.execute('SELECT document FROM records WHERE id=?', (identifier,)).fetchone()
            if result is None:
                continue
            document = json.loads(result[0])
            if document.get('kind') != 'prediction' or digest(document) != identifier:
                raise ValueError('prediction content identity mismatch')
            yield identifier, document
    finally:
        connection.close()
        if checksum() != before:
            raise ValueError('source changed during replay')


def evaluate(expected, memory):
    w = expected['observed_world']
    objects = lambda key: tuple(Object(str(o['id']), Position(*o['position'])) for o in w.get(key, []))
    world = WorldState(w['tick'], Position(*w['player']), objects('targets'),
                       objects('threats'), unresolved=objects('unresolved'),
                       alive=w.get('alive', True), observation_safe=w.get('observation_safe', True))
    brain = Hindbrain(tactical_learning=True, tactical_memory=memory)
    intent, action = brain.decide(world, Goal(**expected['goal']))
    return dict(intent=asdict(intent), action=asdict(action), plan=brain.tactical_plan)


def replay(journals, ledger):
    retained = TacticalDiagnosticMemory(ledger)
    # In-memory ablation only: no source artifact is changed.
    ablated = TacticalDiagnosticMemory(ledger)
    ablated.rows = []
    evidence_predictions = {r['prediction_id'] for r in retained.rows}
    rows = {}
    for path in journals:
        for identifier, document in predictions(path, evidence_predictions - rows.keys()):
            expected = document['payload'].get('expected', document['payload'])
            if 'observed_world' not in expected or 'goal' not in expected:
                continue
            before = evaluate(expected, ablated)
            after = evaluate(expected, retained)
            control = evaluate(expected, ablated)
            assert before == control
            assert before['action'] == after['action']
            rows[identifier] = dict(episode=document['episode'], input_digest=digest(expected),
                source_prediction_id=identifier, baseline=before, retained=after, ablated=control,
                valuation_changed=[a['valuation'] for a in before['plan']['retained_diagnostic']['alternatives']] !=
                    [a['valuation'] for a in after['plan']['retained_diagnostic']['alternatives']],
                preference_changed=before['plan']['retained_diagnostic']['shadow_preference'] !=
                    after['plan']['retained_diagnostic']['shadow_preference'])
    return dict(schema='ala2-retained-tactical-replay-v1', ledger_digest=digest(retained.rows),
                inputs='identical frozen historical interpreted worlds in every arm',
                physical_actions=0, policy_activated=False, rows=list(rows.values()),
                valuation_changes=sum(r['valuation_changed'] for r in rows.values()),
                preference_changes=sum(r['preference_changed'] for r in rows.values()),
                qualification='retrospective diagnostic shadow only; no independent strategy or score qualification')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--journal', action='append', type=Path, required=True)
    p.add_argument('--ledger', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    report = a.report.resolve()
    if report.exists() or report == a.ledger.resolve() or any(
            report == j.resolve() or j.resolve().parent in report.parents for j in a.journal):
        p.error('fresh report outside original journals and ledger required')
    result = replay(a.journal, a.ledger)
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}, indent=2))


if __name__ == '__main__':
    main()
