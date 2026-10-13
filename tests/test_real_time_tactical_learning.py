from dataclasses import replace
import pytest
from experiments.ppal.models import WorldState,Position,Object,Goal,Action
from experiments.ppal.forebrain import Forebrain
from experiments.ppal.hindbrain import Hindbrain


def world(t=0,pos=(50,50),**kw):return WorldState(t,Position(*pos),(Object('rescue',Position(85,50)),),(),**kw)

def feedback(brain,origin,action,resultpos=(50,50),**kw):
    brain.executed_tactic(origin,action,timestamp=10.,track_id='self',prediction_id='prospective-id')
    return brain.tactical_feedback(world(origin.tick+1,resultpos),timestamp=10.2,track_id='self',identity_status='confirmed',
        response_window=dict(endpoint=2,origin_at=10.,move=action.move),**kw)


def test_tactical_options_and_immediate_revision_after_qualified_contradiction():
    b=Hindbrain(tactical_learning=True);w=world();goal=Forebrain().update(w)
    intent,a=b.decide(w,goal);assert a.move=='E' and len(b.tactical_plan['options'])>=8
    out=feedback(b,w,a)
    assert out['eligible'] and out['result']=='contradicted'
    intent,next_action=b.decide(world(1),goal)
    assert next_action.move!='E' and intent.kind=='investigate'
    assert b.tactical_plan['disposition']=='revise after qualified contradiction'


def test_consistent_response_repeats_without_inventing_improvement():
    b=Hindbrain(tactical_learning=True);w=world();g=Forebrain().update(w);_,a=b.decide(w,g)
    r=feedback(b,w,a,(51,50))
    assert r['result']=='supported' and r['displacement']==[1,0]
    _,next_action=b.decide(world(1,(51,50)),g);assert next_action.move=='E'
    assert 'score improvement' in r['interpretation']


@pytest.mark.parametrize('mutation',[{'identity_status':'provisional'},{'track_id':'different'},{'timestamp':10.},
    {'timestamp':13.},{'response_window':dict(endpoint=1,origin_at=10.,move='E')},
    {'response_window':dict(endpoint=2,origin_at=9.,move='E')}])
def test_ambiguous_missing_late_repeated_observations_do_not_penalize(mutation):
    b=Hindbrain(tactical_learning=True);w=world();g=Forebrain().update(w);_,a=b.decide(w,g)
    b.executed_tactic(w,a,timestamp=10.,track_id='self',prediction_id='prediction')
    args=dict(timestamp=10.2,track_id='self',identity_status='confirmed',response_window=dict(endpoint=2,origin_at=10.,move=a.move));args.update(mutation)
    r=b.tactical_feedback(world(1),**args);assert not r['eligible'] and r['result']=='unresolved'
    assert b._tactical_stats=={}
    _,again=b.decide(world(1),g);assert again.move=='E'
    assert b.tactical_feedback(world(2),**args) is None


def test_immediate_threat_and_unsafe_identity_override_adaptation():
    b=Hindbrain(tactical_learning=True);w=world();g=Forebrain().update(w);_,a=b.decide(w,g);feedback(b,w,a)
    danger=replace(world(2),threats=(Object('threat',Position(52,50)),))
    intent,action=b.decide(danger,g);assert intent.kind=='evade' and action.move=='W'
    assert b.tactical_plan['disposition']=='mandatory current-observation override'
    intent,action=b.decide(replace(danger,observation_safe=False),g)
    assert action.move=='STAY' and action.fire=='NONE'


def test_interruption_does_not_create_failed_tactic_or_persistent_policy():
    b=Hindbrain(tactical_learning=True);w=world();g=Forebrain().update(w);_,a=b.decide(w,g)
    b.executed_tactic(w,a,timestamp=10.,track_id='self',prediction_id='prediction')
    r=b.interrupt_tactic('view changed');assert r['resolved_result']=='unresolved'
    assert b._tactical_pending is None and b._tactical_stats=={}
    restart=Hindbrain(tactical_learning=True);_,baseline=restart.decide(w,g);assert baseline.move=='E'


def test_no_executive_or_meditation_in_real_time_path(monkeypatch):
    from memory.learning_projects import LearningExecutive
    from experiments.ppal import meditate_robotron
    monkeypatch.setattr(LearningExecutive,'develop',lambda *a:pytest.fail('Executive turn in gameplay'))
    monkeypatch.setattr(meditate_robotron,'reconstruct_once',lambda *a,**k:pytest.fail('retrospective reconstruction in gameplay'))
    b=Hindbrain(tactical_learning=True);w=world();g=Forebrain().update(w);_,a=b.decide(w,g)
    feedback(b,w,a);b.decide(world(1),g)


def test_viewpoint_epoch_preserves_original_tracks_and_never_recycles_identity():
    from experiments.ppal.robotron_agency import VisualAgency
    from experiments.ppal.eyes.detectors import Detection
    a=VisualAgency();pairs=[(Detection('unknown',(50,50),(10,10,20,20),100),{})]
    a.observe(pairs,observed_at=1);old=list(a.tracker.active);before=a.tracker.describe(a.tracker.active[old[0]])
    assert a.reframe()==old and a.controlled_track_id is None
    assert a.tracker.describe(a.tracker.finished[0])==before
    a.observe(pairs,observed_at=2);assert min(a.tracker.active)>max(old)


def test_bounded_visual_reacquisition_has_no_silent_perfect_view_claim():
    from experiments.ppal.preflight import ImagingMonitor
    from PIL import Image,ImageDraw
    image=Image.new('RGB',(80,60));ImageDraw.Draw(image).rectangle((0,0,79,59),outline='white',width=3)
    m=ImagingMonitor(image,limit=1)
    black=Image.new('RGB',(80,60))
    assert m.observe(black) is None and m.observe(black) is None
    assert m.observe(black)['allowed']
    m.reacquired(image)
    for _ in range(3):r=m.observe(black)
    assert not r['allowed']
