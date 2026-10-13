"""Robotron gameplay/not-gameplay evidence from the calibrated playfield.

This deliberately answers a narrower question than sprite recognition:
does the perimeter look like the mostly single-colour gameplay border, or
like the multi-colour/striped attract border?  Ambiguous frames stay unknown.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def _circular_hue_concentration(hues: np.ndarray) -> float:
    """1.0 means one hue; 0.0 means hues distributed around the circle."""
    if hues.size == 0:
        return 0.0
    angles = hues.astype(np.float32) * (2.0 * np.pi / 180.0)
    return float(np.hypot(np.cos(angles).mean(), np.sin(angles).mean()))


def _border_evidence(playfield: Image.Image) -> dict:
    """Return gameplay/not_gameplay/unknown plus auditable border evidence.

    The calibration maps Robotron's border to the image perimeter.  We sample
    narrow inset bands, retain bright saturated pixels, and compare global hue
    concentration with local hue diversity.  Thresholds are intentionally
    conservative: uncertain imagery must never authorize another START.
    """
    rgb = np.asarray(playfield.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, w = hsv.shape[:2]

    band = max(3, min(h, w) // 80)
    inset = max(2, band)
    pieces = (
        hsv[inset:inset + band, inset:w - inset],
        hsv[h - inset - band:h - inset, inset:w - inset],
        hsv[inset:h - inset, inset:inset + band],
        hsv[inset:h - inset, w - inset - band:w - inset],
    )
    border = np.concatenate([p.reshape(-1, 3) for p in pieces], axis=0)
    colorful = border[(border[:, 1] >= 70) & (border[:, 2] >= 90)]

    coverage = float(len(colorful)) / max(1, len(border))
    if len(colorful) < 80 or coverage < 0.08:
        return {
            "state": "unknown",
            "reason": "insufficient_colored_border",
            "coverage": round(coverage, 4),
        }

    concentration = _circular_hue_concentration(colorful[:, 0])

    # Count occupied hue bins.  Attract's striped border should populate several
    # separated bins; gameplay's single-colour border should be concentrated.
    hist, _ = np.histogram(colorful[:, 0], bins=12, range=(0, 180))
    occupied = int(np.sum(hist >= max(8, int(len(colorful) * 0.025))))

    evidence = {
        "coverage": round(coverage, 4),
        "hue_concentration": round(concentration, 4),
        "occupied_hue_bins": occupied,
    }

    if concentration >= 0.82 and occupied <= 3:
        return {"state": "gameplay", "reason": "uniform_colored_border", **evidence}
    if concentration <= 0.62 and occupied >= 4:
        return {"state": "not_gameplay", "reason": "striped_multicolor_border", **evidence}
    return {"state": "unknown", "reason": "border_ambiguous", **evidence}


# Recorded screen labels extend this existing classifier; no sprite semantics.
# Load/cache small immutable reference masks before gameplay observation begins.
_LABEL_MASKS = None


def _screen_labels(mask):
    global _LABEL_MASKS
    if _LABEL_MASKS is None:
        from pathlib import Path
        directory = Path(__file__).resolve().parents[2]/'config/robotron/screen-labels'
        _LABEL_MASKS = {name:[np.asarray(Image.open(path)) for path in sorted(directory.glob(name+'*.png'))]
                        for name in ('pregame','heroes','all-time')}
    scores={}
    for name,references in _LABEL_MASKS.items():
        target=mask[15:130,80:560] if name!='all-time' else mask[140:300,80:560]
        scores[name]=max(float(cv2.matchTemplate(target,
            cv2.resize(reference,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST),
            cv2.TM_CCOEFF_NORMED).max()) for reference in references for scale in (.85,.925,1.,1.075,1.15))
    return scores


_TITLE_ANCHOR=None

def _title_evidence(mask):
    """Match the complete recorded ROBOTRON + 2084 logo, not a text prefix."""
    global _TITLE_ANCHOR
    import json,hashlib,base64,zlib
    from pathlib import Path
    if _TITLE_ANCHOR is None:
        path=Path(__file__).resolve().parents[2]/'config/robotron/screen-labels/title-anchor.json'
        d=json.loads(path.read_text());raw=zlib.decompress(base64.b64decode(d['zlib_base64']))
        if d['schema']!='recorded-robotron-title-anchor-v1' or hashlib.sha256(raw).hexdigest()!=d['mask_sha256']:
            raise ValueError('recorded title anchor integrity mismatch')
        _TITLE_ANCHOR=(np.frombuffer(raw,dtype=np.uint8).reshape(d['shape']),d)
    anchor,d=_TITLE_ANCHOR
    target=mask[:360,20:620]
    score=max(float(cv2.matchTemplate(target,cv2.resize(anchor,None,fx=scale,fy=scale,
        interpolation=cv2.INTER_NEAREST),cv2.TM_CCOEFF_NORMED).max())
        for scale in (.65,.725,.8,.875,.95,1.,1.05,1.125,1.2,1.275,1.35))
    return dict(matched=score>=d['minimum_similarity'],sha256=d['source_sha256'],
        anchor_sha256=d['mask_sha256'],similarity=score,minimum_similarity=d['minimum_similarity'],
        basis='complete recorded logo pixels; similarity is not a probability')


_GAME_OVER_ANCHOR = None


def _game_over_evidence(mask):
    """Complete recorded GAME OVER words; similarity is not confidence."""
    global _GAME_OVER_ANCHOR
    import json, hashlib, base64, zlib
    from pathlib import Path
    if _GAME_OVER_ANCHOR is None:
        d=json.loads((Path(__file__).resolve().parents[2]/
            'config/robotron/screen-labels/game-over-anchor.json').read_text())
        raw=zlib.decompress(base64.b64decode(d['zlib_base64']))
        if d['schema']!='recorded-robotron-game-over-anchor-v1' or hashlib.sha256(raw).hexdigest()!=d['mask_sha256']:
            raise ValueError('recorded GAME OVER anchor integrity mismatch')
        anchor=np.frombuffer(raw,dtype=np.uint8).reshape(d['shape'])
        _GAME_OVER_ANCHOR=([cv2.resize(anchor,None,fx=x,fy=x,interpolation=cv2.INTER_NEAREST)
            for x in (.85,.925,1.,1.075,1.15)],d)
    anchors,d=_GAME_OVER_ANCHOR
    score=max(float(cv2.matchTemplate(mask[190:285,180:460],a,cv2.TM_CCOEFF_NORMED).max()) for a in anchors)
    return dict(matched=score>=d['minimum_similarity'],similarity=score,
        minimum_similarity=d['minimum_similarity'],sha256=d['source_sha256'],
        anchor_sha256=d['mask_sha256'],basis='complete recorded GAME OVER pixels; similarity is not a probability')


class CurrentScreenClassifier:
    """Reuse only the exact current camera observation, never a later frame."""
    def __init__(self,classifier,key):
        self.classifier=classifier;self.key=key;self.previous=None;self.result=None
        self.calls=0;self.cache_hits=0

    def __call__(self,frame):
        from copy import deepcopy
        key=self.key()
        if key is not None and key==self.previous and self.result is not None:
            self.cache_hits+=1
        else:
            self.result=self.classifier(frame);self.previous=key;self.calls+=1
        return deepcopy(self.result)


def _geometric_border(gray):
    # Complete luminous ridge versus its interior neighbour. Hue-independent;
    # the four sides remain necessary, so bright walls/blank frames do not pass.
    h,w=gray.shape
    bands=((gray[:12,15:w-15].max(axis=0),gray[16:24,15:w-15].mean(axis=0)),
           (gray[-12:,15:w-15].max(axis=0),gray[-24:-16,15:w-15].mean(axis=0)),
           (gray[15:h-15,:12].max(axis=1),gray[15:h-15,16:24].mean(axis=1)),
           (gray[15:h-15,-12:].max(axis=1),gray[15:h-15,-24:-16].mean(axis=1)))
    return [float(((peak>60)&(peak-inside>25)).mean()) for peak,inside in bands]


def classify_screen_state(playfield: Image.Image) -> dict:
    """One screen model: preserve border diagnostics, add explicit phase evidence.

    NOT_GAMEPLAY remains an observation, never START permission. Only a matched
    recorded instruction heading supplies STARTABLE. Heroes headings identify a
    terminal-style display; prior episode context is still needed for game-over.
    """
    base=_border_evidence(playfield)
    rgb=np.asarray(playfield.convert('RGB').resize((640,480)))
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    mask=((gray.astype(float)-cv2.GaussianBlur(gray,(31,31),0).astype(float))>25).astype(np.uint8)*255
    labels=_screen_labels(mask)
    border=_geometric_border(gray)
    title=_title_evidence(mask)
    terminal=_game_over_evidence(mask)
    evidence=dict(base,border_state=base['state'],label_scores={k:round(v,4) for k,v in labels.items()},
                  geometric_border_support=[round(v,4) for v in border],phase='unknown',
                  title_reference=title,terminal_reference=terminal)
    # Scores are template similarities, not probabilities. Simultaneous strong
    # conflicting labels remain UNKNOWN. Prefix similarity alone never suffices.
    heroes=labels['heroes']>=.78 and labels['all-time']>=.78
    pregame=labels['pregame']>=.74 and labels['pregame']-labels['heroes']>=.08
    if terminal['matched']:
        if title['matched'] or heroes or pregame:
            return dict(evidence,state='unknown',reason='conflicting_screen_labels')
        return dict(evidence,state='not_gameplay',phase='terminal',reason='recorded_game_over_message')
    if title['matched'] and (heroes or pregame):
        return dict(evidence,state='unknown',reason='conflicting_screen_labels')
    if title['matched']:
        return dict(evidence,state='not_gameplay',phase='title',reason='recorded_robotron_complete_logo',title_reference=title)
    if heroes and pregame:
        return dict(evidence,state='unknown',reason='conflicting_screen_labels')
    if heroes:
        return dict(evidence,state='not_gameplay',phase='terminal',reason='recorded_heroes_headings')
    if pregame:
        return dict(evidence,state='not_gameplay',phase='startable',reason='recorded_robotron_instruction_heading')
    # Attract border without a recognized page is not safe permission to START.
    if base['state']=='not_gameplay':
        return dict(evidence,state='not_gameplay',reason='unrecognized_striped_page')
    count,_,stats,_=cv2.connectedComponentsWithStats(mask[60:450,20:620],8)
    objects=sum(4<=int(row[4])<=1200 and 2<=int(row[2])<=80 and 2<=int(row[3])<=80
                for row in stats[1:])
    evidence['interior_regions']=objects
    if min(border)>=.65 and objects>=2:
        return dict(evidence,state='gameplay',phase='gameplay',reason='complete_border_and_small_interior_regions')
    if min(border)>=.65:
        return dict(evidence,state='unknown',phase='transition',reason='border_without_active_field_evidence')
    return dict(evidence,state='unknown',reason='insufficient_screen_phase_evidence')


class TaughtTitleReference:
    """One operator-verified visual anchor, not inferred title/GAME OVER text."""
    def __init__(self, declaration):
        import json,hashlib
        from pathlib import Path
        from PIL import Image
        import numpy as np
        path=Path(declaration);d=json.loads(path.read_text())
        if d.get('schema')!='charlie-title-reference-v1' or d.get('verified_by')!='operator':
            raise ValueError('independently verified title reference required')
        image=(path.parent/d['image']).resolve()
        if not image.is_relative_to(path.parent.resolve()) or hashlib.sha256(image.read_bytes()).hexdigest()!=d['sha256']:
            raise ValueError('title reference integrity mismatch')
        roi=d['roi']
        if len(roi)!=4 or not 0<=roi[0]<roi[2]<=1 or not 0<=roi[1]<roi[3]<=1:
            raise ValueError('normalized title marker ROI required')
        self.roi=roi;self.sha256=d['sha256'];self.threshold=d.get('maximum_normalized_error',.04)
        if not 0<self.threshold<=.1:raise ValueError('conservative title matching bound required')
        with Image.open(image) as im:self.template=self._sample(im)
        if float(np.std(self.template))<.05:raise ValueError('title reference lacks discriminating detail')

    def _sample(self,frame):
        import numpy as np
        w,h=frame.size;x0,y0,x1,y1=self.roi
        return np.asarray(frame.convert('RGB').crop((int(w*x0),int(h*y0),int(w*x1),int(h*y1))).resize((64,32)),dtype=float)/255.

    def classify(self,frame):
        import numpy as np
        result=classify_screen_state(frame)
        error=float(np.mean(np.abs(self._sample(frame)-self.template)))
        result['title_reference']=dict(sha256=self.sha256,error=error,matched=error<=self.threshold)
        if error<=self.threshold:
            result.update(state='not_gameplay',phase='title',reason='operator-verified title reference matched')
        return result
