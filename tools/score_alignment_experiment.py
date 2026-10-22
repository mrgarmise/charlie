"""Bounded synthetic alignment control; never authentic recognition evidence."""
import argparse
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from experiments.ppal.neural_score.contract import PREPROCESS,PADDED_PREPROCESS,sha
from experiments.ppal.neural_score.corpus import freeze
from experiments.ppal.neural_score.train import train
from experiments.ppal.neural_score.diagnose import run


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--steps',type=int,default=300);a=p.parse_args()
    if not 1<=a.steps<=2000:raise ValueError('1..2000 bounded fixture steps')
    a.output.mkdir(parents=True,exist_ok=False);rows=[]
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',20)
    for i,label in enumerate(('00','00','00','00','100','800','300','1200')):
        image=Image.new('RGB',(115,96),(i+1,)*3);draw=ImageDraw.Draw(image)
        draw.text((110-draw.textlength(label,font=font),60),label,font=font,fill='white')
        path=a.output/f'fixture-{i}.png';image.save(path)
        rows.append(dict(image=str(path),sha256=sha(path),label=label,verified=True,
            reviewer='SYNTHETIC FIXTURE GENERATOR',annotation_ids=['SYNTHETIC:'+str(i)],
            role='train',session='SYNTHETIC-ALIGNMENT',synthetic=True))
    manifest=a.output/'manifest.json';freeze(rows,manifest);results={}
    for name,profile,weight in (('legacy',PREPROCESS,0.),('padding_only',PADDED_PREPROCESS,0.),
                                ('padding_boundary',PADDED_PREPROCESS,.25)):
        result=train(manifest,a.output/name,steps=a.steps,seed=17,seconds=120,
            preprocessing=profile,boundary_blank_weight=weight)
        diagnostic=run(manifest,a.output/(name+'-audit'),checkpoint=a.output/name/'score.pt',limit=5)
        results[name]=dict(training=result,diagnostic=diagnostic)
    record=dict(scope='SYNTHETIC SOFTWARE CONTROL; NOT authentic accuracy or native qualification',
        source_manifest_sha256=sha(manifest),seed=17,steps=a.steps,results=results,
        independent_validation=False,model_002_accessed=False)
    (a.output/'experiment.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({name:r['diagnostic'] for name,r in results.items()},indent=2))


if __name__=='__main__':main()
