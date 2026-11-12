"""Device-free engineering ablation of the retained positioning interface.

Not a Charlie-originated candidate, qualification, activation, or I1 receipt.
Historical worlds retain their original perception and identity uncertainty.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.replay_retained_tactics import predictions, evaluate
from experiments.ppal.tactical_memory import TacticalDiagnosticMemory, positioning_spec
from experiments.ppal.qualified_policy import QualifiedPolicy
from memory.evidence import digest
from learning.policy import runtime_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', action='append', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = args.report.resolve()
    if report.exists() or report == args.ledger.resolve() or any(
            report == j.resolve() or j.resolve().parent in report.parents for j in args.journal):
        parser.error('fresh report outside original journals and ledger required')
    ledger_bytes = args.ledger.read_bytes()
    retained = TacticalDiagnosticMemory(args.ledger)
    spec = positioning_spec(retained)
    identifiers = {r['prediction_id'] for r in retained.rows}
    rows = {}
    sources = []
    for journal in args.journal:
        sources.append(dict(path=str(journal), sha256=sha256(journal.read_bytes()).hexdigest()))
        for identifier, document in predictions(journal, identifiers - rows.keys()):
            expected = document['payload'].get('expected', document['payload'])
            if 'observed_world' not in expected or 'goal' not in expected:
                continue
            # Direct construction is restricted to this explicitly offline tool.
            # Production uses load_policy and its independent deployment gates.
            policy = QualifiedPolicy.from_payload(dict(spec=spec,
                **{key:'UNACTIVATED-ENGINEERING-ABLATION' for key in
                   ('candidate_id','investigation_id','evaluation_id','activation_key',
                    'rollback_identity','code_revision','provenance_kind')}))
            baseline = evaluate(expected, None)
            adapted = evaluate(expected, policy.tactical_memory, policy)
            ablated = evaluate(expected, None)
            if baseline != ablated:
                raise RuntimeError('non-reproducible ablation')
            rows[identifier] = dict(source_prediction_id=identifier,
                episode=document['episode'], input_sha256=digest(expected),
                baseline=baseline, retained=adapted, ablated=ablated,
                action_changed=baseline['action'] != adapted['action'])
    if args.ledger.read_bytes() != ledger_bytes:
        raise RuntimeError('ledger changed during replay')
    result = dict(schema='experience-action-engineering-ablation-v1',
        runtime_sha256=runtime_hash(), ledger_sha256=sha256(ledger_bytes).hexdigest(),
        learning_state_sha256=spec['retained_tactics']['sha256'], spec=spec,
        source_journals=sources, contexts=len(rows),
        changed_actions=sum(row['action_changed'] for row in rows.values()),
        physical_actions=0, activated=False, charlie_originated_proposal=False,
        qualification='NOT QUALIFIED: engineering interface replay; no physical utility or I1 claim',
        rows=list(rows.values()))
    with report.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','spec')},indent=2))


if __name__ == '__main__':
    main()
