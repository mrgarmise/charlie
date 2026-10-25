"""Additive native-log import/review. Never reruns inference or alters captures."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import html
import json
from pathlib import Path
from memory.evidence import EvidenceJournal
from vision.mobile_tracking import PetTracker


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def recover(events, images, labels, *, output, expected_sha=None, tracker=None):
    import cv2
    events,images,output=Path(events),Path(images),Path(output)
    if expected_sha and sha(events)!=expected_sha:raise ValueError('event log integrity mismatch')
    if events.stat().st_size>32*1024*1024:raise ValueError('bounded native log required')
    original=[json.loads(x) for x in events.read_text().splitlines()]
    if not 1<=len(original)<=10000:raise ValueError('bounded event count required')
    output.mkdir(parents=True,exist_ok=True)
    journal=EvidenceJournal(output/'native-evidence.sqlite3')
    tracker=tracker or PetTracker(loss_seconds=2.)
    tracker.session=sha(events)[:16]  # Deterministic replay IDs, not animal identity.
    counts=Counter();summaries=[];review=[];timeline=[];last=None;ids=set();episode='mobile-native:'+sha(events)
    try:
        for index,event in enumerate(original):
            at=datetime.fromisoformat(event['time_utc']).timestamp()
            if (last is not None and at<=last) or event['frame_id'] in ids or event.get('motion_authorized') is not False:
                raise ValueError('invalid event order/identity/authority')
            last=at;ids.add(event['frame_id'])
            name=event.get('saved_image');annotation=labels.get(name) if name else None
            artifact=None
            if name:
                if Path(name).name!=name:raise ValueError('unsafe capture path')
                path=images/name;im=cv2.imread(str(path))
                if im is None:raise ValueError('missing/invalid original capture')
                pixel=hashlib.sha256(im.tobytes()).hexdigest()
                if pixel!=event['pixel_sha256']:raise ValueError('decoded pixel integrity mismatch')
                artifact=dict(name=name,pixel_sha256=pixel,encoded_sha256=sha(path),geometry=list(im.shape[:2][::-1]))
            frame=dict(id=event['frame_id'],received_at=at,geometry=artifact['geometry'] if artifact else [800,600],
                       pan_deg=None,yaw_deg=None,authentic=True,source_age_known=False)
            # UTC event time is only the historical replay timeline, not a
            # synchronized source exposure clock or current monotonic timestamp.
            tracking=tracker.update(dict(frame=frame,objects=event['detections']))
            raw=journal.append('observation',dict(category='mobile_native_prediction',raw=event,artifact=artifact,
                label_coverage='operator-reviewed' if annotation else 'unlabeled',timestamp_basis='historical UTC event'),
                episode=episode,at=at,producer='native-log-import',version='mobile-evidence-v2',
                provenance=dict(events_sha256=sha(events),original_order=index,source_software_sha=None))
            if annotation:
                if not artifact:raise ValueError('annotation requires original pixels')
                journal.append('observation',dict(category='mobile_operator_annotation',annotation=annotation,artifact=artifact),
                    episode=episode,at=at,sources=[raw.id],producer='operator-label-import',version='mobile-evidence-v2')
                counts['annotated_frames']+=1
                predicted=[d for d in event['detections'] if d['label'] in ('cat','dog')]
                for d in predicted:
                    counts['correct_species' if d['label']==annotation['species'] else 'wrong_species']+=1
                    counts['predicted_'+d['label']]+=1
                overlay=im.copy()
                for d in predicted:
                    x,y,r,b=map(round,d['box']);cv2.rectangle(overlay,(x,y),(r,b),(0,200,255),2)
                cv2.putText(overlay,f"{annotation['subject']} ({annotation['species']}, operator); model: "+','.join(d['label'] for d in predicted),(8,22),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,200,255),1)
                dest=output/(Path(name).stem+'-review.png')
                if not cv2.imwrite(str(dest),overlay):raise OSError('overlay export failed')
                review.append(f'<article><h2>{html.escape(name)}</h2><img width="600" src="{dest.name}"><pre>{html.escape(json.dumps(dict(time=event["time_utc"],prediction=predicted,tracking=tracking),indent=2))}</pre></article>')
                summaries.append(dict(artifact=artifact,predicted_species=[d['label'] for d in predicted],annotation=annotation,
                    track_ids=[t['id'] for t in tracking['tracks'] if t['observed']],at=at))
            timeline.append(dict(frame_id=event['frame_id'],at=at,tracking=tracking))
        summary=dict(events=len(original),events_sha256=sha(events),annotated_frames=counts['annotated_frames'],
            unlabeled_events=len(original)-counts['annotated_frames'],classification=dict(counts),captures=summaries,
            independent_animals='operator reports Monty in nine reviewed images; not nine independent animals',
            detection_recall=None,localization_accuracy=None,qualification='historical replay, not new native inference',motion_commands=0)
        # The terminal fault is supplied by operator; never pretend it was in log.
        journal.append('event',dict(category='mobile_native_reported_fault',error='TimeoutError',
            source='operator mission',message='Timed out waiting for fresh Elegoo camera frame',
            present_in_original_log=False),episode=episode,producer='operator-report-import',version='mobile-evidence-v2')
        (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        (output/'tracking.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in timeline))
        (output/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Private pet evidence review</title><h1>Historical stationary review — no motion</h1><p>Raw model predictions and separate operator annotations. Remaining events unlabeled. Track IDs are hypotheses.</p>'+''.join(review))
        return summary
    finally:journal.close()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events',type=Path,required=True);p.add_argument('--images',type=Path,required=True)
    p.add_argument('--labels',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--expected-events-sha')
    a=p.parse_args(argv)
    result=recover(a.events,a.images,json.loads(a.labels.read_text()),output=a.output,expected_sha=a.expected_events_sha)
    print(json.dumps({k:v for k,v in result.items() if k!='captures'}))

if __name__=='__main__':main()
