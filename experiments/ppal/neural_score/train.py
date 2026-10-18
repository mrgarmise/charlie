"""Real whole-string CTC training, resumable weights/optimizer and fixed ONNX export."""
import argparse
import json
from pathlib import Path
import random
import signal
import time
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from .contract import preprocess,sha,INPUT,BLANK
from .corpus import freeze,verify,assert_trainable,image_path


def synthetic(output,*,seed=17,count=96):
    output=Path(output);output.mkdir(exist_ok=False);rng=random.Random(seed);rows=[]
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
    font=ImageFont.truetype(font_path,24)
    special=['0','11','100','2200','3500','9999999','']
    for i in range(count):
        role='train' if i<count*.7 else 'val' if i<count*.85 else 'test'
        label=special[i%len(special)] if i<28 else str(rng.randrange(100000))
        image=Image.new('RGB',(256,32),({'train':0,'val':24,'test':48}[role]+rng.randrange(8),)*3);draw=ImageDraw.Draw(image)
        text_width=draw.textlength(label,font=font)
        draw.text((244-text_width,0),label,font=font,fill=(rng.randrange(180,256),)*3)
        path=output/f'{i:04d}.png';image.save(path)
        role='train' if i<count*.7 else 'val' if i<count*.85 else 'test'
        # Shared synthetic font correlations are explicitly NOT independent games.
        rows.append(dict(image=str(path),sha256=sha(path),label=label,role=role,session='SYNTHETIC-'+role,
            reviewer='engineering fixture generator; NOT human Robotron review',verified=True,
            annotation_ids=[f'SYNTHETIC:{seed}:{i}'],synthetic=True,channel=1))
    return freeze(rows,output/'manifest.json')


def train(manifest,output,*,steps=100,seed=17,batch=8,resume=None,seconds=120):
    import torch
    from .model import ScoreNet,export
    if not 1<=steps<=100000 or not 1<=batch<=32 or not 1<=seconds<=86400:raise ValueError('bounded training controls required')
    record=assert_trainable(manifest);data=[r for r in record['rows'] if r['role']=='train' and r['label'] is not None]
    if not data:raise ValueError('no eligible whole-string training labels')
    output=Path(output);output.mkdir(exist_ok=False)
    torch.set_num_threads(2);torch.manual_seed(seed);rng=random.Random(seed);np.random.seed(seed)
    model=ScoreNet();optimizer=torch.optim.Adam(model.parameters(),lr=.001)
    start_step=0
    if resume:
        state=torch.load(resume,map_location='cpu',weights_only=True)
        if state['dataset_digest']!=record['digest']:raise ValueError('resume dataset mismatch')
        model.load_state_dict(state['state_dict']);optimizer.load_state_dict(state['optimizer']);start_step=state['step']
        torch.set_rng_state(state['torch_rng']);rng.setstate(state['python_rng'])
    initial={k:v.detach().clone() for k,v in model.state_dict().items()}
    criterion=torch.nn.CTCLoss(blank=BLANK,zero_infinity=False)
    stopped=[]
    old=signal.signal(signal.SIGTERM,lambda *a:stopped.append(True))
    begin=time.monotonic();losses=[];step=start_step
    try:
        for step in range(start_step,start_step+steps):
            if stopped or time.monotonic()-begin>seconds:break
            selected=[rng.choice(data) for _ in range(batch)];inputs=[];targets=[];lengths=[]
            for row in selected:
                with Image.open(image_path(manifest,row)) as image:x,_=preprocess(image)
                inputs.append(x[0]);targets.extend(int(c) for c in row['label']);lengths.append(len(row['label']))
            logits=model(torch.from_numpy(np.stack(inputs)))[:,:,0,:].permute(2,0,1).log_softmax(2)
            loss=criterion(logits,torch.tensor(targets,dtype=torch.long),torch.full((batch,),64,dtype=torch.long),torch.tensor(lengths))
            if not torch.isfinite(loss):raise ValueError('nonfinite CTC training loss')
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5.);optimizer.step()
            losses.append(float(loss.detach()))
    finally:signal.signal(signal.SIGTERM,old)
    checkpoint=dict(architecture='score-conv-ctc-v1',state_dict=model.state_dict(),optimizer=optimizer.state_dict(),
        dataset_digest=record['digest'],step=start_step+len(losses),seed=seed,torch_rng=torch.get_rng_state(),python_rng=rng.getstate(),
        qualification=record['authenticity'],parameters=dict(lr=.001,batch=batch,loss='CTC blank=10',augmentation='none; training originals only',input=list(INPUT)))
    pt=output/'score.pt';torch.save(checkpoint,pt)
    changed=any(not torch.equal(initial[k],v) for k,v in model.state_dict().items())
    onnx=output/'score.onnx';export_report=export(pt,onnx)
    result=dict(schema='charlie-score-training-v1',qualification=record['authenticity'],dataset_digest=record['digest'],
        seed=seed,steps=len(losses),total_steps=checkpoint['step'],weights_changed=changed,losses=losses,
        seconds=time.monotonic()-begin,checkpoint_sha256=sha(pt),onnx_sha256=sha(onnx),export=export_report,
        resume_sha256=sha(resume) if resume else None,hef_created=False,hardware_validated=False)
    (output/'training.json').write_text(json.dumps(result,indent=2));return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--synthetic',type=Path)
    p.add_argument('--manifest',type=Path);p.add_argument('--output',type=Path);p.add_argument('--steps',type=int,default=100)
    p.add_argument('--resume',type=Path);p.add_argument('--seconds',type=int,default=120)
    a=p.parse_args()
    if a.synthetic:synthetic(a.synthetic)
    if a.output:
        if not a.manifest:p.error('--manifest required for training')
        print(json.dumps(train(a.manifest,a.output,steps=a.steps,resume=a.resume,seconds=a.seconds),indent=2))

if __name__=='__main__':main()
