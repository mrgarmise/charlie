"""Raw full-string recognition metrics, separate from temporal score acceptance."""
import math
import statistics


def edit(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        nxt=[i]
        for j,y in enumerate(b,1):nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(x!=y)))
        row=nxt
    return row[-1]


def wilson(hits,n):
    if not n:return None
    z=1.96;p=hits/n;d=1+z*z/n;mid=(p+z*z/(2*n))/d
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [mid-half,mid+half]


def metrics(rows):
    labeled=[r for r in rows if r['label'] is not None];readable=[r for r in labeled if r['label']!='']
    accepted=[r for r in readable if r['prediction']['score'] is not None]
    correct=sum(r['prediction']['digits']==r['label'] for r in accepted)
    negative=[r for r in labeled if r['label']=='']
    durations=sorted(r['wall_seconds'] for r in rows)
    return dict(samples=len(rows),readable=len(readable),accepted=len(accepted),correct=correct,
        coverage=len(accepted)/len(readable) if readable else None,
        exact_accuracy_at_coverage=correct/len(accepted) if accepted else None,
        exact_over_all_readable=correct/len(readable) if readable else None,
        correct_over_all_wilson95=wilson(correct,len(readable)),
        total_digit_edit_distance=sum(edit(r['prediction'].get('digits') or '',r['label']) for r in readable),
        high_confidence_wrong=sum(r['prediction']['confidence']>=.9 and r['prediction']['digits']!=r['label'] for r in accepted),
        no_score_samples=len(negative),no_score_false_positives=sum(r['prediction']['score'] is not None for r in negative),
        p1_p2_swaps='unmeasured without paired channel truth',quantization_drift='unmeasured without real HEF',
        latency={f'p{q}':durations[min(len(durations)-1,math.ceil(q/100*len(durations))-1)] if durations else None for q in (50,95,99)})


def quantization_comparison(reference,candidate):
    import numpy as np
    from .contract import OUTPUT,decode
    a=np.asarray(reference);b=np.asarray(candidate)
    if a.shape!=OUTPUT or b.shape!=OUTPUT or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('parity shape/nonfinite mismatch')
    ra,rb=decode(a),decode(b)
    return dict(maximum_absolute_logit_error=float(np.abs(a-b).max()),
        mean_absolute_logit_error=float(np.abs(a-b).mean()),
        proposed_digits_match=ra['proposed_digits']==rb['proposed_digits'],
        accepted_digits_match=ra['digits']==rb['digits'],
        reference_confidence=ra['confidence'],candidate_confidence=rb['confidence'])
