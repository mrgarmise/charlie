"""Operator-run x86_64 export bridge using the separate Vision Lab checkout.

No dependency installation, downloads of weights, training, camera or deployment.
"""
import argparse
import importlib.metadata
import json
import platform
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab-state',required=True,type=Path)
    p.add_argument('--model-id',required=True)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):
        raise RuntimeError('DFC compilation requires supported Linux x86_64 host')
    from vision_lab.store import Lab,file_hash
    from vision_lab.datasets import verify_manifest,export_yolo
    lab=Lab(a.lab_state);model=lab.get('models',a.model_id)
    manifest=verify_manifest(lab,model['dataset_id'])
    if manifest['digest']!=model['dataset_digest']: raise ValueError('model dataset mismatch')
    pt=lab.root/'models'/a.model_id/'best.pt'
    if file_hash(pt)!=model['checkpoint_sha256']: raise ValueError('weights integrity mismatch')
    # Export into fresh workspace; original model/state files remain intact.
    a.output.mkdir(parents=True,exist_ok=False)
    import shutil
    copy=a.output/'best.pt';shutil.copyfile(pt,copy)
    dataset=export_yolo(lab,model['dataset_id'])
    train=[r for r in manifest['frames'] if r['role']=='train']
    if not train: raise ValueError('no verified training calibration imagery')
    # Deliberately point BOTH exporter roles at train. No validation/test leakage.
    config=dict(path=str(dataset.resolve()),train='train/images',val='train/images',names=manifest['classes'],nc=len(manifest['classes']))
    yaml=a.output/'calibration-train-only.yaml';yaml.write_text(json.dumps(config))
    import ultralytics
    from ultralytics.engine.exporter import export_formats
    formats=export_formats()
    if 'hailo' not in formats['Argument']: raise RuntimeError('installed Ultralytics has no Hailo exporter; use separate compiler environment')
    dfc=importlib.metadata.version('hailo-dataflow-compiler')
    if not dfc.startswith('3.'): raise RuntimeError('hailo8l requires DFC v3.x')
    record=dict(schema='charlie-hailo-export-v1',architecture='hailo8l',model=model,
        dataset_digest=manifest['digest'],calibration_frames=train,calibration_count=len(train),
        calibration_constraint='below recommended 1024' if len(train)<1024 else None,
        ultralytics=ultralytics.__version__,dfc=dfc,qualification='UNQUALIFIED; no hardware execution',hef_created=False)
    log=a.output/'export.json';log.write_text(json.dumps(record,indent=2))
    result=ultralytics.YOLO(str(copy)).export(format='hailo',name='hailo8l',data=str(yaml),imgsz=model['parameters']['imgsz'],fraction=1.)
    hefs=list(Path(result).rglob('*.hef'))
    if len(hefs)!=1: raise RuntimeError('expected exactly one actual compiled HEF')
    record.update(hef_created=True,hef_path=str(hefs[0]),hef_sha256=file_hash(hefs[0]),classes=manifest['classes'],
                  imgsz=model['parameters']['imgsz'],decoder='hailo-nms-yxyx-score')
    log.write_text(json.dumps(record,indent=2))
    print(log)


if __name__=='__main__':main()
