"""Parent-side heldout evaluation; training worker never receives test rows."""
from collections import Counter
import statistics
import time
from .adapters import get_adapter


def metrics(truth,predicted,*,labels=None):
    labels=labels or get_adapter().labels
    matrix={label:{other:0 for other in labels} for label in labels}
    for actual,result in zip(truth,predicted): matrix[actual][result]+=1
    classes={}
    for label in labels:
        tp=matrix[label][label]; support=sum(matrix[label].values()); emitted=sum(matrix[x][label] for x in labels)
        classes[label]=dict(precision=tp/emitted if emitted else 0.,recall=tp/support if support else 0.,support=support)
    return dict(confusion=matrix,per_class=classes,macro_recall=statistics.mean(c['recall'] for c in classes.values()),
        accuracy=sum(a==b for a,b in zip(truth,predicted))/max(1,len(truth)),
        abstention=sum(p=='unknown' for p in predicted)/max(1,len(predicted)),
        false_positives=sum(a!=p and p!='unknown' for a,p in zip(truth,predicted)))


def evaluate(model,snapshot,*,on_progress=None,wall_seconds=10.):
    adapter=get_adapter(snapshot['task'])
    frame,incumbent,predict=adapter.frame,adapter.incumbent,adapter.predict
    rows=[r for r in snapshot['rows'] if r['partition']=='test']
    truth=[]; predictions=[]; baseline=[]; latency=[]; failures=[]
    majority=Counter(r['label'] for r in snapshot['rows'] if r['partition']=='train').most_common(1)[0][0]
    started=time.monotonic()
    for row in rows:
        if on_progress:on_progress()
        if time.monotonic()-started>wall_seconds:raise InterruptedError('independent evaluation wall budget exceeded')
        image=frame(row); start=time.perf_counter(); result=predict(model,image)
        latency.append((time.perf_counter()-start)*1000)
        truth.append(row['label']); predictions.append(result['label']); baseline.append(incumbent(image))
        if row['label']!=result['label']: failures.append(dict(observation_id=row['observation_id'],actual=row['label'],**result))
    return dict(candidate=metrics(truth,predictions,labels=adapter.labels),incumbent=metrics(truth,baseline,labels=adapter.labels),non_ml_majority=metrics(truth,[majority]*len(rows),labels=adapter.labels),
        failures=failures,latency_ms=dict(median=statistics.median(latency),maximum=max(latency)),
        test_observations=[r['observation_id'] for r in rows],test_sessions=sorted({r['session'] for r in rows}),
        authentic=all(r['authentic'] for r in snapshot['rows']),hardware='host CPU only',
        calibration='not established; distances are not probabilities',
        transitions='not measured: independent still frames lack complete timed sequences',
        resources=dict(worker=model.get('worker_resources'),native='not measured'))
