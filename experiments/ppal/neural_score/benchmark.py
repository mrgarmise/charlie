"""Host saved-camera comparison; no hardware and no independent qualification."""
import argparse
import json
from pathlib import Path
import statistics
import time
from PIL import Image
from ..eyes.calibration import Calibration
from ..eyes.sprites import regions
from ..robotron_hud import RobotronHUDReader
from .backends import CPU
from .contract import preprocess,decode,sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--onnx',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--exemplars',type=Path)
    a=p.parse_args();root=Path(__file__).resolve().parents[3]/'tests/fixtures/robotron-tracking-score'
    labels=json.loads((root/'labels.json').read_text());first=Image.open(root/'camera-zero.jpg')
    cal=Calibration.from_pixels(labels['diagnostic_corners_pixels'],first.size);fixed=RobotronHUDReader(cal)
    exemplar=None
    if a.exemplars:
        from ..score_feedback import ScoreFeedbackReader
        exemplar=ScoreFeedbackReader.load(a.exemplars,cal)
    cpu=CPU(a.onnx,sha(a.onnx));rows=[]
    for name,label in labels['scores'].items():
        with Image.open(root/name) as original:raw=original.convert('RGB')
        for repeat in range(5):
            begin=time.perf_counter();cpu_start=time.process_time();baseline=fixed.read(raw);fixed_seconds=time.perf_counter()-begin
            begin=time.perf_counter();hud=fixed.rectify(raw);crops=[]
            for fraction in (fixed.P1_X,fixed.P2_X):
                crop=hud.crop((int(640*fraction[0]),0,int(640*fraction[1]),96));x,pre=preprocess(crop)
                values,timing=cpu.infer(x);crops.append(dict(decode(values),timing=timing))
            neural_seconds=time.perf_counter()-begin
            begin=time.perf_counter();regions(raw);sprite_seconds=time.perf_counter()-begin
            rows.append(dict(image=name,original_sha256=sha(root/name),historical_p1_label=label,
                fixed_p1=baseline.player1_score,fixed_p2=baseline.player2_score,neural_channels=crops,
                exemplar_p1=exemplar.read(raw).player1_score if exemplar else None,
                exemplar_status='explicit offline candidate' if exemplar else 'unavailable; no recovered reviews',
                repeat=repeat,fixed_seconds=fixed_seconds,neural_seconds=neural_seconds,sprite_cpu_seconds=sprite_seconds,
                combined_cpu_reference_seconds=neural_seconds+sprite_seconds,process_cpu_seconds=time.process_time()-cpu_start))
    result=dict(schema='charlie-score-host-comparison-v1',native=False,independent_heldout=False,authentic_training_labels=0,
        qualification='two historical JPEG regressions with diagnostic geometry; not new original human reviews',
        source_labels=labels,model_sha256=sha(a.onnx),samples=rows,
        median_seconds={key:statistics.median(r[key] for r in rows) for key in ['fixed_seconds','neural_seconds','sprite_cpu_seconds','combined_cpu_reference_seconds']},
        real_hailo_inference=False,joint_hailo_cpu_headroom='UNMEASURED',capture_timestamps='unavailable in JPEG label provenance; none fabricated')
    with a.output.open('x') as out:json.dump(result,out,indent=2)

if __name__=='__main__':main()
