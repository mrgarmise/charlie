"""Robotron adapter: reuse calibrated observations and incumbent; never capture."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from experiments.ppal.eyes.calibration import Calibration
from .data import sha

SCREEN_STATE_LABELS=('title_menu','gameplay','terminal','unknown')
PREPROCESSING='rgb-spatial-16x12-v1'
INCUMBENT_FILE=str(Path(__file__).resolve().parents[2]/'experiments/ppal/robotron_screen_state.py')


def frame(row):
    if sha(row['path'])!=row['sha256']: raise ValueError('frame digest changed')
    with Image.open(row['path']) as image: result=image.convert('RGB')
    if row.get('calibration'):
        result=Calibration(tuple(tuple(p) for p in row['calibration']['corners'])).apply(result)
    return result


def features(image):
    return np.asarray(image.convert('RGB').resize((16,12)),dtype=np.float64).reshape(-1)/255.


def incumbent(image):
    from experiments.ppal.robotron_screen_state import classify_screen_state
    phase=classify_screen_state(image)['phase']
    return dict(title='title_menu',startable='title_menu',gameplay='gameplay',terminal='terminal').get(phase,'unknown')


def predict(model,image):
    if model.get('preprocessing')!=PREPROCESSING or model.get('runtime')!='numpy-cpu-json-v1':
        raise ValueError('unsupported inference contract')
    if set(model["centroids"])!={"title_menu","gameplay","terminal"}:raise ValueError("model label schema changed")
    for center in model["centroids"].values():
        a=np.asarray(center)
        if a.shape!=(576,) or not np.isfinite(a).all(): raise ValueError("invalid centroid shape/values")
    if not 0<model["radius"]<=.3 or not 0<model["margin"]<=1:raise ValueError("invalid abstention contract")
    x=features(image)
    distances=sorted((float(np.sqrt(np.mean((x-np.asarray(center))**2))),label) for label,center in model['centroids'].items())
    distance,label=distances[0]
    margin=distances[1][0]-distance if len(distances)>1 else 0.
    accepted=distance<=model['radius'] and margin>=model['margin'] and np.std(x)>.01
    return dict(label=label if accepted else 'unknown',distance=distance,margin=margin,
                confidence=None,calibration='uncalibrated distance; not probability',mode='shadow')


def import_fixtures(store,repo):
    root=Path(repo)/'tests/fixtures/robotron-screen-states'
    added=[]
    for row in json.loads((root/'provenance.json').read_text()):
        rec=store.add(root/row['path'],session=row['source_run'],provenance=row,authentic=True,calibration=row['calibration'])
        label=dict(startable='title_menu',gameplay='gameplay',terminal='terminal')[row['expected_phase']]
        if not any(r.data['payload']['observation_id']==rec.id for r in store.events('model_label')):
            store.label(rec.id,label,reviewer='existing-repository-regression',reason='preserved expected_phase; fallible test annotation')
        added.append(rec.id)
    failed=Path(repo)/'tests/fixtures/robotron-failed-start-031501'
    provenance=json.loads((failed/'provenance.json').read_text())
    images=list(failed.glob('*.png'))
    if images:
        if sha(images[0])!=provenance['sha256']: raise ValueError('original fixture hash mismatch')
        rec=store.add(images[0],session='marathon-20261008-031501',provenance=provenance,authentic=True)
        added.append(rec.id) # Deliberately no title label: source says unverified.
    return added


def localization_annotation(*,frame_sha256,session,objects,reviewer):
    """Separate detector schema. A screen label never supplies coordinates."""
    if not frame_sha256 or not session or not reviewer: raise ValueError('source attribution required')
    for obj in objects:
        if obj['class'] not in ('player','enemy','projectile','obstacle','unknown'): raise ValueError('separate object vocabulary required')
        x0,y0,x1,y1=obj['box']
        if not 0<=x0<x1<=1 or not 0<=y0<y1<=1: raise ValueError('normalized bounding box required')
        if not 0<=obj['uncertainty']<=1: raise ValueError('bounded uncertainty required')
    return dict(schema='robotron-localization-v1',frame_sha256=frame_sha256,session=session,objects=objects,reviewer=reviewer,
                track_identity='session-local only; annotation does not establish physical identity')


def localization_proposals(recording,*,max_frames=8):
    """Reuse saved PPAL blob proposals on authentic rectified frames, no detector training.

    Machine boxes and historical track names are not independently annotated
    ground truth. Keep their semantic labels UNKNOWN until separately reviewed.
    """
    if type(max_frames) is not int or not 1<=max_frames<=32:raise ValueError('bounded replay required')
    root=Path(recording);source=root/'detections.json'
    if source.stat().st_size>16*1024**2:raise ValueError('recording metadata too large')
    original=json.loads(source.read_text());result=[]
    for row in original['frames'][:max_frames]:
        tick=row['tick'];image=root/'tracking/playfields'/('playfield_'+format(tick,'03d')+'.jpg')
        if not image.is_file():continue
        with Image.open(image) as im:w,h=im.size
        objects=[]
        for detection in row['detections'][:128]:
            x0,y0,x1,y1=detection['box']
            if not 0<=x0<x1<=w or not 0<=y0<y1<=h:continue
            objects.append(dict(**{'class':'unknown'},box=[x0/w,y0/h,x1/w,y1/h],uncertainty=1.,
                candidate_kind=detection['kind'],track_id=None))
        annotation=localization_annotation(frame_sha256=sha(image),session=root.name,objects=objects,reviewer='unreviewed-existing-PPAL-proposals')
        result.append(dict(annotation,source_metadata_sha256=sha(source),captured_at_seconds=row.get('captured_at_seconds'),
            tick=tick,coordinates='rectified saved playfield',truth=False))
    return dict(schema='robotron-localization-proposals-v1',frames=result,semantic_accuracy=None,
        localization_accuracy=None,source='existing saved PPAL proposals, no new inference or capture',
        limitations=['machine boxes unverified','no object identity inheritance','single recording is not independent holdout'])
