"""Frozen-reader replay of preserved camera-derived regression images.

No model training, authentic feedback replacement, hardware or activation.
"""
import argparse,hashlib,json,time,subprocess,types,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.robotron_hud import RobotronHUDReader
from memory.evaluator import MemoryEvaluator
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline-ref',default='708a1f6b5177497f4e765dd1900fa8407d266d8c');parser.add_argument('--output',type=Path)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
folder=repo/'tests/fixtures/robotron-tracking-score';labels=json.loads((folder/'labels.json').read_text())
# Replay the exact unmodified agency reader as a frozen code baseline.
source=subprocess.check_output(['git','show',args.baseline_ref+':experiments/ppal/robotron_hud.py'],cwd=repo,text=True)
baseline=types.ModuleType('experiments.ppal.frozen_score_baseline');baseline.__package__='experiments.ppal';sys.modules[baseline.__name__]=baseline;exec(compile(source,'frozen-reader','exec'),baseline.__dict__)
image=Image.open(folder/'camera-zero.jpg');cal=Calibration.from_pixels(labels['diagnostic_corners_pixels'],image.size)
rows=[]
for name,label in labels['scores'].items():
    with Image.open(folder/name) as raw:
        start=time.perf_counter();before=baseline.RobotronHUDReader(cal).read(raw);base_seconds=time.perf_counter()-start
        start=time.perf_counter();after=RobotronHUDReader(cal).read(raw);new_seconds=time.perf_counter()-start
    rows.append(dict(image=name,sha256=hashlib.sha256((folder/name).read_bytes()).hexdigest(),label=label,
        baseline=before.player1_score,baseline_confidence=before.player1_confidence,
        candidate=after.player1_score,confidence=after.player1_confidence,baseline_seconds=base_seconds,seconds=new_seconds))
report=dict(schema='score-recognition-preserved-camera-regression-v1',original_reader_source=args.baseline_ref,baseline_reader_sha256=hashlib.sha256(source.encode()).hexdigest(),label_source=labels,
    samples=rows,baseline=MemoryEvaluator.score_recognition_metrics(rows,'baseline'),candidate=MemoryEvaluator.score_recognition_metrics(rows,'candidate'),
    feedback_applied=False,October10_reviews_recovered=False,independent_heldout=False,
    interpretation='Authentic camera-derived JPEG regression only; existing historical labels, no recovered October 10 update or generalization claim',native_pi_measurement=False,physical_authorization=False)
if args.output:
    with args.output.open('x') as output:output.write(json.dumps(report,indent=2)+'\n')
else:print(json.dumps(report,indent=2))
