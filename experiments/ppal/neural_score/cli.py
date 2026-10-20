"""Saved raw-frame/crop replay only. Opens neither camera nor controller nor writer."""
import argparse
import json
from pathlib import Path
import time
from PIL import Image
from .contract import preprocess,decode,sha,PREPROCESS
from .backends import CPU,Hailo,Backend
from .reader import NeuralHUDReader
from .corpus import image_path,verify,consult_test
from .evaluate import metrics,quantization_comparison


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--onnx',type=Path)
    p.add_argument('--mode',choices=['cpu-reference','hailo-required','hailo-preferred'],default='cpu-reference')
    p.add_argument('--model-record',type=Path);p.add_argument('--hef',type=Path);p.add_argument('--hef-contract',type=Path)
    p.add_argument('--manifest',type=Path);p.add_argument('--role',choices=['train','val','test'],default='val')
    p.add_argument('--frame',type=Path);p.add_argument('--calibration',type=Path)
    p.add_argument('--compare-reference',action='store_true');p.add_argument('--source',type=Path,help='JSON with observation_id, exposure_at, timestamp_basis, original capture metadata')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    contract=json.loads(a.hef_contract.read_text()) if a.hef_contract else None
    model_sha=sha(a.onnx) if a.onnx else None
    model_record=json.loads(a.model_record.read_text()) if a.model_record else None
    if model_record and model_record['onnx_sha256']!=model_sha:raise ValueError('model record/ONNX mismatch')
    if contract and model_sha and contract['onnx_sha256']!=model_sha:raise ValueError('HEF/CPU checkpoint mismatch')
    profile=(model_record or contract or {}).get('preprocessing',PREPROCESS)
    if contract and contract.get('preprocessing',PREPROCESS)!=profile:raise ValueError('HEF/CPU preprocessing mismatch')
    backend=Backend(a.mode,lambda:CPU(a.onnx,model_sha,preprocessing=profile),lambda:Hailo(a.hef,contract) if a.hef and contract else (_ for _ in ()).throw(RuntimeError('HEF absent')))
    with a.output.open('x') as out:
        if a.frame:
            from ..eyes.calibration import Calibration
            from ..robotron_hud import RobotronHUDReader
            if not a.calibration or not a.source:p.error('raw frame requires calibration and actual source metadata')
            source=json.loads(a.source.read_text());at=source['exposure_at']
            reader=NeuralHUDReader(Calibration.load(a.calibration),backend,dict(onnx_sha256=model_sha,hef=contract,training_record=model_record,architecture='score-conv-ctc-v1'),clock=lambda:at)
            reader.bind_source(t=at,source=source)
            with Image.open(a.frame) as image:
                raw=image.convert('RGB');reader.read(raw);fixed=vars(RobotronHUDReader(reader.calibration).read(raw))
            packet=reader.last_packet;packet.update(original_image_sha256=sha(a.frame),fixed_reader_baseline=fixed,
                replay=True,image_age_seconds=None,qualification='recorded pixels; historical replay is not native freshness')
            out.write(json.dumps(packet)+'\n')
            if a.mode=='hailo-required' and any(r.get('health_event') for r in packet['channels']):raise SystemExit(2)
        else:
            reference=CPU(a.onnx,model_sha,preprocessing=profile) if a.compare_reference else None
            corpus=verify(a.manifest);rows=[]
            if a.role=='test':consult_test(a.manifest)
            for row in corpus['rows']:
                if row['role']!=a.role:continue
                start=time.perf_counter()
                with Image.open(image_path(a.manifest,row)) as image:x,pre=preprocess(image,profile=profile)
                try:values,timing=backend.infer(x);prediction=decode(values)
                except Exception as exc:prediction=dict(score=None,digits=None,confidence=0.,reason=f'{type(exc).__name__}: {exc}');timing=None
                parity=None
                if reference is not None and timing is not None and timing.get('backend')=='hailo-required':
                    control,_=reference.infer(x);parity=quantization_comparison(control,values)
                result=dict(parity=parity,label=row['label'],image_sha256=row['sha256'],session=row['session'],channel=row.get('channel'),
                    prediction=prediction,wall_seconds=time.perf_counter()-start,timing=timing,preprocessing=pre)
                rows.append(result);out.write(json.dumps(result)+'\n')
            report=dict(metrics=metrics(rows),qualification=corpus['authenticity'],manifest_sha256=sha(a.manifest),mode=a.mode,
                onnx_sha256=model_sha,model_record=model_record,hef=contract,raw_recognition_only=True,native_hailo_inference=any((r['timing'] or {}).get('backend')=='hailo-required' for r in rows),native_camera_latency_measured=False)
            report_path=a.output.with_suffix(a.output.suffix+'.metrics.json')
            with report_path.open('x') as stream:json.dump(report,stream,indent=2)
            print(json.dumps(report,indent=2))
            if a.mode=='hailo-required' and any(r['timing'] is None for r in rows):raise SystemExit(2)

if __name__=='__main__':main()
