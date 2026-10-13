"""Causal controls over software fixtures; not ALA learning acceptance."""
from copy import deepcopy
from memory.learning_projects import LearningExecutive


def project(name, units=0, trials=0):
    return dict(id=name, status='candidate', method='diagnostic', requires=[],
                dependencies=[], uncertainty=1., objective_contribution=.5,
                learning_value=.5, cost=.5, risk=.5,
                progress=dict(resolved=trials, independent_physical_episodes=0,
                              independent_offline_evidence_units=units),
                experiment_history=[dict(result='supported', resolution_id='fixture-'+str(n))
                                    for n in range(trials)])


def choose(projects):
    executive=object.__new__(LearningExecutive)
    executive.projects=lambda:deepcopy(projects)
    return executive.select(methods={'diagnostic'}, resources=set(),
                            authorized_methods={'diagnostic'}, inspect=True)


def test_retained_independent_outcome_changes_selection_under_identical_alternatives():
    before={'z':project('z'), 'a':project('a')}
    assert choose(before)['project']['id']=='z'
    after=deepcopy(before);after['z']=project('z',1,1)
    selected=choose(after)
    assert selected['project']['id']=='a'
    assert before['z']['progress']['resolved']==0
    trace=next(a for a in selected['alternatives'] if a['project_id']=='z')
    assert trace['experience_basis']['resolution_ids']==['fixture-0']
    # Same runtime, choices, resources, permissions and tie-break; only retained
    # diagnostic experience is ablated. No random exploration is involved.
    assert choose(before)['project']['id']=='z'


def test_correlated_repeated_outcomes_cannot_further_reduce_uncertainty():
    one=choose({'z':project('z',1,1)})['alternatives'][0]
    repeated=choose({'z':project('z',1,8)})['alternatives'][0]
    assert one['score']==repeated['score']
    assert repeated['terms']['remaining_uncertainty']==.5
    assert repeated['experience_basis']['independent_units']==1


def test_unknown_and_unaccounted_legacy_outcomes_cannot_reduce_uncertainty():
    legacy=project('z',0,8);legacy['progress']={'resolved':8}
    assert choose({'z':legacy})['alternatives'][0]['terms']['remaining_uncertainty']==1.
    unresolved=project('z');unresolved['experiment_history']=[dict(result='unresolved',resolution_id='unknown')]
    trace=choose({'z':unresolved})['alternatives'][0]
    assert trace['terms']['remaining_uncertainty']==1.
    assert trace['experience_basis']['resolution_ids']==[]


def test_priority_control_preserves_authority_holds_and_active_project_stickiness():
    state={'z':project('z',1,1),'a':project('a')};state['z']['status']='active'
    assert choose(state)['project']['id']=='z'
    state['z']['hold']=True
    assert choose(state)['project']['id']=='a'
    state['a']['method']='unauthorized'
    assert choose(state)['project'] is None


def test_actual_journal_reload_and_reused_episode_priority(tmp_path):
    from memory.evidence import EvidenceJournal
    from test_learning_projects import gateway, hypothesis, result, select
    j=EvidenceJournal(tmp_path/'notebook.sqlite3');e=LearningExecutive(j,gateway(tmp_path))
    p=hypothesis(j);identifier=e.propose(p['proposal'],j,[p['evidence_id']]);select(e)
    condition=dict(p['proposal']['scope'],setting='a')
    result(e,identifier,j,condition=condition,episode='same-original-episode')
    first=e.select(methods={'opaque-test-method'},resources=set(),
                   authorized_methods={'opaque-test-method'},inspect=True)['alternatives'][0]
    result(e,identifier,j,condition=condition,episode='same-original-episode')
    j.close();j=EvidenceJournal(tmp_path/'notebook.sqlite3');e=LearningExecutive(j,gateway(tmp_path))
    later=e.select(methods={'opaque-test-method'},resources=set(),
                   authorized_methods={'opaque-test-method'},inspect=True)['alternatives'][0]
    assert first['score']==later['score']
    assert later['experience_basis']['independent_units']==1
    assert len(later['experience_basis']['resolution_ids'])==2
    j.close()


def test_read_only_audit_does_not_grant_acceptance_or_modify_source(tmp_path):
    from memory.evidence import EvidenceJournal
    from learning.causal_audit import audit
    from learning.datasets import sha
    from test_learning_projects import gateway, hypothesis, result, select
    path=tmp_path/'notebook.sqlite3';j=EvidenceJournal(path);e=LearningExecutive(j,gateway(tmp_path))
    p=hypothesis(j);identifier=e.propose(p['proposal'],j,[p['evidence_id']]);select(e)
    result(e,identifier,j,condition=dict(p['proposal']['scope'],setting='a'),episode='fixture')
    select(e);j.close();before=sha(path)
    report=audit(path)
    assert report['priority_influence_controls']==1
    assert report['source_unchanged'] and sha(path)==before
    assert report['gates']=={k:'NOT YET DEMONSTRATED' for k in ('E1','P1','I1')}
    assert not report['physical_authorization'] and not report['retained_activation_records']
