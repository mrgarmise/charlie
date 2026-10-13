"""Clearly synthetic fixture generator and optional real CPU pipeline smoke run."""
import argparse
import json
from pathlib import Path
import time
from PIL import Image,ImageDraw
from .store import Lab
from .sources import add_source,index_source,hydrate
from .datasets import freeze
from .jobs import Jobs


def create(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);originals=output/'SYNTHETIC-ONLY'
    lab=Lab(output/'lab-state');lab.set_classes(['player','grunt'])
    for session in range(4):
        folder=originals/f'fixture-session-{session}';folder.mkdir(parents=True)
        for number in range(2):
            im=Image.new('RGB',(96,96),(12+session*5,20+number*6,35));draw=ImageDraw.Draw(im)
            draw.rectangle((10+number,12,30+number,36),fill='#00ccff');draw.rectangle((60,55+session,80,78+session),fill='#ff5577');im.save(folder/f'sample-{number}.png')
    source=add_source(lab,dict(kind='local',root=str(originals),name='SYNTHETIC ENGINEERING FIXTURES',authenticity='synthetic-fixture',group_depth=1));index_source(lab,source['id'])
    frames=lab.frames()
    for f in frames:
        hydrate(lab,f['id']);session=int(f['locator'].split('/')[0].split('-')[-1]);number=int(Path(f['locator']).stem.split('-')[-1])
        boxes=[dict(x=10+number,y=12,w=20,h=24,class_name='player',confidence=1,uncertain=False,accepted=True,origin='synthetic-fixture'),dict(x=60,y=55+session,w=20,h=23,class_name='grunt',confidence=1,uncertain=False,accepted=True,origin='synthetic-fixture')]
        lab.annotate(f['id'],dict(revision=0,status='verified',boxes=boxes,reviewer='Synthetic fixture generator; not human Robotron review',note='Known generated shapes; engineering data only'))
    dataset=freeze(lab,'Synthetic engineering smoke dataset',[f['id'] for f in frames],None)
    return lab,dataset


def wait(lab,job,seconds=600):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        row=lab.get('jobs',job['id'])
        if row['status'] in ('completed','failed','cancelled','interrupted'):
            if row['status']!='completed':raise RuntimeError(str(row))
            return row['result']
        time.sleep(.2)
    raise TimeoutError('Bounded smoke job deadline exceeded')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--train',action='store_true');ap.add_argument('--export',action='store_true');args=ap.parse_args()
    lab,dataset=create(args.output);report=dict(state=str(lab.root),dataset_id=dataset['id'],fixture_only=True,physical_authorization=False)
    if args.train:
        jobs=Jobs(lab)
        try:
            model=wait(lab,jobs.submit('train',dict(dataset_id=dataset['id'],epochs=1,imgsz=64,batch=2,threads=2,device='cpu')));report['model']=model
            report['evaluation']=wait(lab,jobs.submit('evaluate',dict(model_id=model['id'],dataset_id=dataset['id'],partition='test',baseline_id=None)))
            if args.export:report['export']=wait(lab,jobs.submit('export',dict(model_id=model['id'])))
        finally:jobs.close()
    (args.output/'engineering-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
