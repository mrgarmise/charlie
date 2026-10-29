"""Explicit user policy evaluated outside training, and rechecked at approval."""
import math
DEFAULT_GATES=dict(min_macro_recall=.9,min_unknown_recall=.9,max_latency_ms=100.,min_test_per_class=5)


def gates(value=None):
    result=dict(DEFAULT_GATES)
    if value:
        if set(value)-set(result):raise ValueError('unknown qualification gate')
        result.update(value)
    for name,low,high in [('min_macro_recall',0.,1.),('min_unknown_recall',0.,1.),('max_latency_ms',1.,1000.)]:
        item=result[name]
        if isinstance(item,bool) or not isinstance(item,(float,int)) or not math.isfinite(item) or not low<=item<=high:
            raise ValueError('invalid '+name)
    if type(result['min_test_per_class']) is not int or not 1<=result['min_test_per_class']<=100:
        raise ValueError('bounded heldout support required')
    return result


def reasons(metrics,policy):
    policy=gates(policy);candidate=metrics['candidate'];result=[]
    if not metrics['authentic']: result.append('synthetic plumbing only')
    if not metrics['fresh_holdout']: result.append('holdout previously consulted')
    if candidate['macro_recall']<policy['min_macro_recall']:result.append('macro recall below gate')
    if candidate['per_class']['unknown']['recall']<policy['min_unknown_recall']:result.append('unknown abstention below gate')
    if any(c['support']<policy['min_test_per_class'] for c in candidate['per_class'].values()):result.append('insufficient per-class heldout support')
    if candidate['macro_recall']<=max(metrics[k]['macro_recall'] for k in ('incumbent','non_ml_majority')):result.append('no measured baseline improvement')
    if metrics['latency_ms']['maximum']>policy['max_latency_ms']:result.append('host latency exceeds gate')
    return result
