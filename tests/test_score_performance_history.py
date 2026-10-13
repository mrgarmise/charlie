"""Controlled certificate interface fixtures, not physical game evidence."""
import pytest
from experiments.ppal.inspect_robotron_score import performance_history,freeze_baseline,baseline_history
from test_robotron_score_comparison import setup
from test_robotron_qualified_comparison import certified


def test_qualified_history_frozen_baseline_and_rolling_exclusions(tmp_path):
    j,plan,protocol=setup(tmp_path);rows=[]
    for n in range(30):
        root=tmp_path/str(n);root.mkdir()
        row,frames,proof=certified(j,protocol,root)
        # Distinct original source reports, not renamed copies of one trial.
        import json
        from learning.datasets import sha
        source=root/'report.json';source.write_text(json.dumps({'controlled_game':n}))
        old_episode=row['source_episode'];episode='episode:'+sha(source)
        boundary=j.get(row['boundary_certificate']).data['payload']
        boundary.update(source_episode=episode,source_report={'path':str(source),'sha256':sha(source)})
        b=j.append('observation',boundary,episode=protocol.data['episode'],producer='independent-physical-measurement',version='fixture')
        score=j.get(row['score_observations'][0]['validation_evidence']).data['payload']
        score.update(source_episode=episode,boundary_certificate=b.id)
        c=j.append('observation',score,episode=protocol.data['episode'],producer='independent-physical-measurement',version='fixture')
        row.update(source_episode=episode,boundary_certificate=b.id)
        row['score_observations'][0]['validation_evidence']=c.id
        r=j.append('observation',row,episode=protocol.data['episode'],producer='test-fixture',version='controlled')
        rows.append(r.id)
        if n==8:
            h=performance_history(j)[row['policy']];assert h['qualified_games']==9 and h['rolling']['10'] is None
    policy=row['policy'];h=performance_history(j)[policy]
    assert h['qualified_games']==30 and h['rolling']['10']['mean']==1200 and h['rolling']['30']['count']==30
    baseline=freeze_baseline(j,'frozen fixture',policy,rows[:10]);assert baseline.data['payload']['count']==10
    assert freeze_baseline(j,'frozen fixture',policy,rows[:10]).id==baseline.id
    with pytest.raises(ValueError,match='replaced'):freeze_baseline(j,'frozen fixture',policy,rows[10:20])
    with pytest.raises(ValueError,match='qualified'):freeze_baseline(j,'wrong policy','different-policy',rows[:10])
    # An alias evaluation record cannot inflate counts.
    duplicate=j.get(rows[-1]).data['payload']
    j.append('observation',duplicate,episode=protocol.data['episode'],producer='test-fixture',version='alias')
    assert performance_history(j)[policy]['qualified_games']==30
    # Corrupt proof invalidates current eligibility, preserving frozen history.
    (tmp_path/'0'/'proof.txt').write_text('corrupt fixture')
    assert baseline_history(j)[0]['currently_qualified'] is False
    assert j.get(baseline.id).data['payload']['count']==10
    j.verify();j.close()
