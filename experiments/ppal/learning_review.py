"""Review live evidence without promoting diagnostic guesses into learned facts."""
import argparse
from collections import Counter
import json
from pathlib import Path


def review_session(output, games):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    groups = {}
    episodes = []
    for game in games:
        path = Path(game['path'])/'report.json'
        try:
            report = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        counts = Counter(s.get('status') for s in report.get('steps', []))
        issues = []
        if report.get('score') is None:
            issues.append(('score', 'What score did this run actually reach, and was it a full game or a timed segment?'))
        if report.get('episode_end',{}).get('confirmed') is not True:
            issues.append(('episode_end', 'At the end, was this game over, a life loss, a level transition, or tracking failure?'))
        if any(counts[k] for k in ('reacquiring','player_reacquired','control_challenge')):
            issues.append(('self_identity', 'Which sprite is Charlie immediately before and after the recorded identity loss?'))
        for kind, question in issues:
            group = groups.setdefault(kind, {'id':'robotron-review:'+kind,'status':'open','question':question,'examples':[]})
            group['examples'].append({'report':str(path), 'events':dict(counts), 'evidence_frames':report.get('review_frames',[])})
        episodes.append({'report':str(path), 'result':report.get('result'), 'score':report.get('score'),
                         'eligible_for_score_comparison': not issues and report.get('armed') is True})
    result={'schema':'charlie-live-review-v1','objective':'maximize_score','episodes':episodes,
            'questions':list(groups.values()),
            'learning_status':'diagnostics_only_no_policy_update',
            'note':'Repeated questions are grouped, not repeated once per game. Missing labels remain unknown.'}
    (output/'learning-review.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('episodes',nargs='+',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    r=review_session(a.output,[{'path':str(x)} for x in a.episodes])
    print(f"Reviewed {len(r['episodes'])} episodes; {len(r['questions'])} grouped questions")


if __name__=='__main__': main()
