"""Fixed score-sequence contract and conservative, non-calibrated CTC decoding."""
import hashlib
import math
import numpy as np
from PIL import Image
from ..score_digits import valid_display_digits

SCHEMA='charlie-neural-score-v1'
PREPROCESS='score-rgb-channel-resize-256x32-v1'
PADDED_PREPROCESS='score-rgb-channel-resize-224x28-pad16x2-v2'
PREPROCESS_PROFILES=(PREPROCESS,PADDED_PREPROCESS)
DECODER='ctc-greedy-abstain-v1'
INPUT=(1,3,32,256)
OUTPUT=(1,11,1,64)
BLANK=10


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def preprocess(image, *, profile=PREPROCESS):
    """No glyph segmentation or inferred digits: retain complete channel aspect."""
    image=image.convert('RGB');w,h=image.size
    if not 1<=w<=4096 or not 1<=h<=2048:raise ValueError('bounded source crop required')
    # The calibrated fixed channel contains large vertical margins. Map the
    # complete channel to fixed dimensions instead of squeezing its word into
    # a few CTC timesteps. No content-dependent digit/glyph trimming.
    if profile not in PREPROCESS_PROFILES:raise ValueError('unknown score preprocessing profile')
    # 224/256 == 28/32: preserve the legacy input aspect while adding fixed
    # margins. This is not a content-dependent crop or an aspect correction.
    size,padding=((256,32),(0,0)) if profile==PREPROCESS else ((224,28),(16,2))
    canvas=Image.new('RGB',(256,32))
    canvas.paste(image.resize(size,Image.Resampling.BILINEAR),padding)
    array=np.asarray(canvas,dtype=np.float32)/255.
    return np.transpose(array,(2,0,1))[None],dict(version=profile,scale_xy=[size[0]/w,size[1]/h],padding=list(padding),
        input_shape=list(INPUT),color='RGB',range=[0,1],resize='bilinear full-channel fixed aspect transform',source_size=[w,h])



def decode(logits, *, min_score=.85, min_margin=.25, max_digits=7):
    values=np.asarray(logits,dtype=np.float64)
    if values.shape!=OUTPUT or not np.isfinite(values).all():raise ValueError('sequence tensor shape/nonfinite mismatch')
    values=values[0,:,0,:].T
    shifted=values-values.max(axis=1,keepdims=True);p=np.exp(shifted);p/=p.sum(axis=1,keepdims=True)
    path=p.argmax(axis=1);ordered=np.sort(p,axis=1);conf=ordered[:,-1];margins=ordered[:,-1]-ordered[:,-2]
    runs=[]
    for i,token in enumerate(path):
        if not runs or runs[-1]['token']!=int(token):runs.append(dict(token=int(token),start=i,end=i+1,score=float(conf[i]),margin=float(margins[i])))
        else:
            runs[-1]['end']=i+1
            runs[-1]['score']=min(runs[-1]['score'],float(conf[i]))
            runs[-1]['margin']=min(runs[-1]['margin'],float(margins[i]))
    digits=[r for r in runs if r['token']!=BLANK]
    text=''.join(str(r['token']) for r in digits)
    reason=None
    # Check every timestep: uncertain blank could conceal a missing digit.
    if not digits:reason='blank/no score'
    elif len(text)>max_digits:reason='length exceeds contract'
    elif path[0]!=BLANK or path[-1]!=BLANK:reason='edge/truncated sequence'
    elif len(text)>1 and text[0]=='0' and set(text)!={'0'}:reason='noncanonical leading zero; no coercion'
    elif not valid_display_digits(text):reason='unsupported Robotron visible digits; no coercion'
    elif float(conf.min())<min_score or float(margins.min())<min_margin:reason='ambiguous digit or blank'
    score=float(conf.min())
    return dict(score=int(text) if reason is None else None,digits=text if reason is None else None,
        proposed_digits=text,confidence=score,uncertainty='uncalibrated softmax minimum; not probability of correct score',
        reason=reason,decoder=DECODER,alignment_runs=runs,
        diagnostic_logits=np.round(values,5).tolist())


def crop_quality(image):
    rgb=np.asarray(image.convert('RGB'));level=rgb.max(axis=2)
    if level.max()<40:return 'blank or severely dim crop'
    if (level>250).mean()>.6:return 'glare/overexposed crop'
    mask=level>max(40,float(np.percentile(level,99))*.5)
    if mask[:,0].any() or mask[:,-1].any() or mask[0].any() or mask[-1].any():return 'edge clipping or channel bleed'
    return None


def finite(v):return type(v) in (int,float) and math.isfinite(v)
