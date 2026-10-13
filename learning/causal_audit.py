"""Read-only Executive outcome ablation; mechanistic evidence, not gate closure.

Replays the existing chooser at historical selections without commissioning work,
constructing memories, changing the source notebook or activating any policy.
Historical runtime/inputs and independent authenticity remain separate checks.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess

from memory.evidence import EvidenceJournal, digest
from memory.learning_projects import LearningExecutive
from .datasets import sha


class Prefix:
    def __init__(self, rows):
        self.rows=rows

    def records(self, kind=None):
        return [r for r in self.rows if kind is None or r.data['kind']==kind]


def replay(projects, environment):
    # No __init__: consolidation is a writer. inspect=True cannot write or clear
    # a hold. Both controls use the exact same deployed selection implementation.
    executive=object.__new__(LearningExecutive)
    executive.projects=lambda:deepcopy(projects)
    result=executive.select(**environment, inspect=True)
    return dict(selected=result['project']['id'] if result['project'] else None,
                alternatives=result['alternatives'])


def ablate_priority_experience(projects):
    state=deepcopy(projects)
    for p in state.values():
        progress=p.setdefault('progress',{})
        progress['independent_physical_episodes']=0
        progress['independent_offline_evidence_units']=0
    return state


def selection_controls(journal):
    rows=journal.records();controls=[]
    for index,row in enumerate(rows):
        payload=row.data['payload']
        if row.data['producer']!='LearningExecutive' or payload.get('op')!='selected':
            continue
        projects=LearningExecutive.project_state(Prefix(rows[:index]))
        alternatives=payload.get('alternatives',[])
        if not alternatives:
            continue
        # These are reconstructed *read-only* diagnostic inputs, never grants.
        # Compare only if they reproduce the archived eligibility/alternative set.
        environment=dict(methods={projects[a['project_id']]['method'] for a in alternatives if a['method_available']},
            authorized_methods={projects[a['project_id']]['method'] for a in alternatives if a['authorized']},
            resources=set().union(*(set(projects[a['project_id']].get('requires',[]))-set(a['missing_resources']) for a in alternatives)),
            urgent_projects={a['project_id'] for a in alternatives if a.get('urgent')})
        retained=replay(projects,environment)
        absent=replay(ablate_priority_experience(projects),environment)
        expected={a['project_id']:bool(a['blocked']) for a in alternatives}
        reproduced={a['project_id']:bool(a['blocked']) for a in retained['alternatives']}
        deltas=[]
        for learned,control in zip(retained['alternatives'],absent['alternatives']):
            if learned['project_id']!=control['project_id']:
                raise ValueError('causal controls changed alternatives')
            if learned['score']==control['score']:
                continue
            h=projects[learned['project_id']].get('experiment_history',[])
            outcomes=[v for v in h if v['result']!='unresolved']
            bindings=[]
            for outcome in outcomes:
                try:
                    resolution=journal.get(outcome['resolution_id'])
                    matched=(resolution.sequence<row.sequence and resolution.data['kind']=='resolution'
                        and resolution.data['payload']['result']==outcome['result']
                        and resolution.data['payload']['prediction_id']==outcome['prediction_id'])
                    bindings.append(dict(resolution_id=resolution.id,available=True,matched=matched,
                        sources=resolution.data['sources']))
                except KeyError:
                    bindings.append(dict(resolution_id=outcome['resolution_id'],available=False,
                        matched=False,reason='original source journal required; reference is not an observation'))
            deltas.append(dict(project_id=learned['project_id'],
                retained_score=learned['score'],ablated_score=control['score'],
                retained_uncertainty=learned['terms']['remaining_uncertainty'],
                ablated_uncertainty=control['terms']['remaining_uncertainty'],
                independent_units=learned['experience_basis']['independent_units'],
                outcome_bindings=bindings))
        controls.append(dict(selection_id=row.id,sequence=row.sequence,
            observed_historical_choice=payload['project_id'],
            environment={k:sorted(v) for k,v in environment.items()},
            eligibility_reproduced=expected==reproduced,
            retained_choice=retained['selected'],ablated_choice=absent['selected'],
            choice_changed=retained['selected']!=absent['selected'],priority_changes=deltas,
            context_digest=digest(projects),
            control='Only independent experience counts ablated; histories, opportunities, lifecycle, permissions, resources and runtime fixed',
            limitation='Current-runtime retrospective control; not a new investigation, archived-runtime equivalence, authenticity certification or E1 pass'))
    return controls


def audit(path):
    path=Path(path).resolve()
    before=sha(path)
    journal=EvidenceJournal(path,read_only=True)
    try:
        controls=selection_controls(journal)
        projects=LearningExecutive.project_state(journal)
        activations=[r.id for r in journal.category_records('event','capability_activation')]
        return dict(schema='ala2-causal-audit-v1',source_journal_sha256=before,
            source_records=len(journal.records()),project_ids=sorted(projects),
            source_content_digest=digest([r.id for r in journal.records()]),
            source_unchanged=before==sha(path),controls=controls,
            matching_eligibility_controls=sum(c['eligibility_reproduced'] for c in controls),
            priority_influence_controls=sum(bool(c['priority_changes']) and c['eligibility_reproduced'] for c in controls),
            changed_choice_controls=sum(c['choice_changed'] and c['eligibility_reproduced'] for c in controls),
            retained_activation_records=activations,
            gates={k:'NOT YET DEMONSTRATED' for k in ('E1','P1','I1')},
            limitations=['Hash integrity does not certify authentic observations or measurement independence',
                'Priority ablation does not remove outcome-dependent lifecycle/hold or Evaluator feedback',
                'Archived choice may differ from current runtime; no historical equivalence inferred',
                'P1 requires authentic transitions, retained learning update, reload and comparable PPAL decisions',
                'I1 requires independent qualification, separate authority, downstream influence and rollback',
                'This report cannot activate, commission, supply observations or close acceptance gates'],
            physical_authorization=False)
    finally:
        journal.close()
        if sha(path)!=before:
            raise ValueError('source notebook changed during causal audit')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('journal',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();source=args.journal.resolve();target=args.output.resolve()
    if source.parent==target.parent or source.parent in target.parents:
        raise ValueError('report must be outside the original notebook')
    result=audit(source)
    result['runtime_revision']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    result['runtime_dirty']=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip())
    result['selection_runtime_sha256']=sha(Path(__file__).resolve().parents[1]/'memory/learning_projects.py')
    with target.open('x') as file:
        json.dump(result,file,indent=2,allow_nan=False);file.write('\n')
    print(json.dumps({k:result[k] for k in ('source_records','priority_influence_controls','changed_choice_controls','gates')}))


if __name__=='__main__':
    main()
