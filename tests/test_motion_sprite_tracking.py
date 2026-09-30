"""Motion prediction and whole-world association, including real endpoint data."""
from itertools import permutations
import json
import math
from pathlib import Path
import random

import pytest
from PIL import Image, ImageDraw

from experiments.ppal.eyes.detectors import Detection
from experiments.ppal.eyes.tracking import SpriteTracker, _assignment
from experiments.ppal.eyes.sprites import regions
from experiments.ppal.robotron_session import PersistentSelfTracker
from experiments.ppal.play_robotron import _objects, HUMANS, THREATS

FIXTURE=Path(__file__).parent/'fixtures/robotron-agency-first'


def d(x,y=50,kind='unknown',box=(0,0,10,20)):
    return Detection(kind,(x,y),box,100)


def test_global_assignment_keeps_owner_of_stationary_neighbor():
    t=SpriteTracker(); first=t.update(0,[d(10),d(14)])
    second=t.update(1,[d(13),d(14.2)])
    assert second==first  # the neighbor owns its near-zero displacement match


def test_elapsed_prediction_handles_longer_observation_interval():
    t=SpriteTracker(max_distance=7)
    first=t.update(0,[d(10)],observed_at=10.)
    t.update(1,[d(16)],observed_at=10.1)
    third=t.update(2,[d(28)],observed_at=10.3)
    assert third==first
    row=t.last_update['predictions'][0]
    assert row['predicted']==pytest.approx([28,50])
    assert row['candidates'][0]['prediction_error']==pytest.approx(0.)


def test_tick_only_prediction_also_handles_fast_continuous_motion():
    t=SpriteTracker()
    first=t.update(0,[d(10)])
    t.update(1,[d(16)])
    assert t.update(2,[d(24)])==first


def test_stop_and_reversal_do_not_force_new_identity():
    t=SpriteTracker(); first=None
    for tick,x in enumerate([10,20,20,10,10,20]):
        assigned=t.update(tick,[d(x)],observed_at=tick*.15)
        first=assigned if first is None else first
        assert assigned==first


def test_time_gap_predicts_occluded_motion_without_stale_position():
    t=SpriteTracker()
    first=t.update(0,[d(10)],observed_at=0.)
    t.update(1,[d(14)],observed_at=.1)
    t.update(2,[],observed_at=.2)
    assert t.update(3,[d(22)],observed_at=.3)==first
    assert t.active[first[0]].velocity==pytest.approx((40,0))


def test_many_simultaneously_moving_sprites_keep_physical_ids():
    t=SpriteTracker(); expected=None
    for tick in range(12):
        detections=[d(10+i*14+tick*.7,10+j*14+tick*.4)
                    for i in range(5) for j in range(5)]
        ids=t.update(tick,detections,observed_at=tick*.08)
        expected=ids if expected is None else expected
        assert ids==expected
    assert t.next_id==26


def test_prediction_resolves_a_crossing_between_frames():
    t=SpriteTracker(); first=t.update(0,[d(10),d(22)])
    assert t.update(1,[d(14),d(18)])==first
    assert t.update(2,[d(18),d(14)])==first
    assert t.update(3,[d(22),d(10)])==first


def test_unresolved_merge_quarantines_previous_identities():
    t=SpriteTracker(); first=t.update(0,[d(40),d(42)])
    merged=t.update(1,[d(41)])
    assert merged[0] not in first.values()
    assert all(t.active[ident].identity_uncertain for ident in first.values())
    separated=t.update(2,[d(40),d(42)])
    assert not set(first.values()).intersection(separated.values())
    assert any(e['kind']=='ambiguous' for e in t.last_update['events'])


def test_three_object_cyclic_ambiguity_is_not_hidden_by_pairwise_matches():
    t=SpriteTracker(max_distance=30)
    def triangle(angle):
        return [d(50+10*math.cos(angle+i*2*math.pi/3),
                  50+10*math.sin(angle+i*2*math.pi/3)) for i in range(3)]
    first=t.update(0,triangle(0))
    second=t.update(1,triangle(math.pi/3))
    assert not set(first.values()).intersection(second.values())
    assert sum(e['kind']=='ambiguous' for e in t.last_update['events'])==3


def test_labels_can_transform_without_renaming_physical_track():
    t=SpriteTracker(); first=t.update(0,[d(20,kind='mom')])
    for tick,kind in enumerate(['unknown','grunt','unknown'],1):
        assert t.update(tick,[d(20+tick,kind=kind)])==first
    track=t.active[first[0]]
    assert track.kinds==['mom','unknown','grunt','unknown']
    assert [row['kind'] for row in t.describe(track)['semantic_history']]==track.kinds


def test_world_role_change_preserves_generic_id_and_excludes_self():
    assignments={0:42,1:6}
    family=[(d(20,kind='mom'),{}),(d(50,kind='mom'),{})]
    hostile=[(d(21,kind='grunt'),{}),(d(50,kind='grunt'),{})]
    assert _objects(family,HUMANS,'human',assignments,6)[0].id=='sprite_42'
    assert _objects(hostile,THREATS,'threat',assignments,6)[0].id=='sprite_42'
    assert len(_objects(family,HUMANS,'human',assignments,6))==1


def test_bind_existing_track_does_not_run_association_twice():
    generic=SpriteTracker(); ids=generic.update(0,[d(50)],observed_at=1.)
    self_tracker=PersistentSelfTracker(tracker=generic)
    assert self_tracker.bind_track(0,ids[0],{ids[0]:(50,50)}).center==(50,50)
    assert generic.active[ids[0]].observations==1


def test_same_frame_reseed_in_legacy_replay_uses_cached_assignment():
    t=PersistentSelfTracker(); t.seed(0,[d(50)],(50,50))
    detections=[d(52)]
    t.update(1,detections)
    t.reseed(1,detections,(52,50))
    assert t.tracker.active[t.player_track_id].observations==2


def test_telemetry_explains_creation_match_miss_ambiguity_and_expiry():
    t=SpriteTracker(max_missed=1)
    t.update(0,[d(40),d(42)])
    assert all(e['kind']=='created' for e in t.last_update['events'])
    t.update(1,[d(41)])
    assert any(e['kind']=='ambiguous' for e in t.last_update['events'])
    t.update(2,[])
    assert any(e['kind']=='expired' for e in t.last_update['events'])
    assert any(e['kind']=='missed' for e in t.last_update['events'])
    assert t.last_update['predictions']
    t.update(3,[d(80)])
    t.update(4,[d(81)])
    event=next(e for e in t.last_update['events'] if e['kind']=='matched')
    assert event['cost'] is not None and event['margin'] is not None
    assert t.last_update['detections'][0]['track_id']==event['track_id']


def test_implausible_teleport_is_new_track_even_with_elapsed_time():
    t=SpriteTracker(); first=t.update(0,[d(10)],observed_at=0.)
    second=t.update(1,[d(80)],observed_at=.1)
    assert first!=second
    assert t.last_update['predictions'][0]['rejected_counts']['travel']==1


@pytest.mark.parametrize('timestamps', [[1,1],[1,.5],[1,float('nan')]])
def test_bad_clocks_are_rejected(timestamps):
    t=SpriteTracker(); t.update(0,[d(10)],observed_at=timestamps[0])
    with pytest.raises(ValueError):t.update(1,[d(10)],observed_at=timestamps[1])


def test_elapsed_and_tick_clocks_cannot_be_mixed():
    t=SpriteTracker(); t.update(0,[d(10)],observed_at=0.)
    with pytest.raises(ValueError):t.update(1,[d(11)])


def test_hungarian_matches_brute_force_optimum_for_small_worlds():
    rng=random.Random(42)
    for _ in range(30):
        costs=[[rng.uniform(-3,20) for _ in range(5)] for _ in range(3)]
        assigned=_assignment(costs)
        actual=sum(costs[i][j] for i,j in enumerate(assigned))
        expected=min(sum(costs[i][j] for i,j in enumerate(choice)) for choice in permutations(range(5),3))
        assert actual==pytest.approx(expected)
        assert len(set(assigned))==3


def test_blue_screen_background_is_not_a_candidate():
    frame=Image.new('RGB',(640,480),(5,30,170));draw=ImageDraw.Draw(frame)
    draw.rectangle((90,150,101,175),fill='white')
    draw.rectangle((300,100,315,120),fill=(255,20,20))
    draw.rectangle((500,300,515,320),fill=(5,30,255))
    boxes=[box for box,_,_ in regions(frame)]
    assert len(boxes)==3
    assert any(b[0]==500 for b in boxes)  # blue sprite still detectable
    assert not any((b[2]-b[0])>100 for b in boxes)


def test_local_background_gradient_and_border_are_not_sprites():
    import numpy as np
    rgb=np.zeros((480,640,3),dtype=np.uint8)
    rgb[:,:,2]=np.linspace(145,190,640).astype(np.uint8)
    frame=Image.fromarray(rgb);draw=ImageDraw.Draw(frame)
    draw.rectangle((30,10,630,470),outline='white',width=3)
    draw.rectangle((200,200,210,220),fill='white')
    boxes=[b for b,_,_ in regions(frame)]
    assert boxes==[(200,200,211,221)]


def test_real_unannotated_startup_does_not_yield_whole_screen_blob():
    frame=Image.open(FIXTURE/'startup-000.png')
    found=regions(frame)
    assert len(found)>10  # old detector yielded only 3, swallowing visible processes
    assert max(area for _,area,_ in found)<5000
    assert all(box!=(5,5,635,475) for box,_,_ in found)


def test_recorded_endpoint_geometry_keeps_isolated_stationary_object():
    fixture=json.loads((FIXTURE/'endpoints.json').read_text())
    t=SpriteTracker(); at=0; mine_id=None
    # The isolated star-shaped object near (33.5,83.3) is visually persistent.
    # This fixture has no original boxes or exact capture times; it tests only
    # the recorded geometry, not true player identity or full live acquisition.
    for tick,row in enumerate(fixture['samples']):
        at+=row['interval_seconds']
        ds=[d(*candidate['center'],kind=candidate['kind']) for candidate in row['candidates']]
        assigned=t.update(tick,ds,observed_at=at)
        index=min(range(len(ds)),key=lambda i:math.dist(ds[i].center,(33.5,83.3)))
        assert math.dist(ds[index].center,(33.5,83.3))<.3
        mine_id=assigned[index] if mine_id is None else mine_id
        assert assigned[index]==mine_id
    assert t.next_id-1<131  # legacy replay created 131 IDs from these 272 endpoints
