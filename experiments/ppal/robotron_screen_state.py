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
        _LABEL_MASKS = {name:np.asarray(Image.open(directory/f'{name}.png'))
                        for name in ('pregame','heroes','all-time')}
    scores={}
    for name,reference in _LABEL_MASKS.items():
        target=mask[15:130,80:560] if name!='all-time' else mask[140:300,80:560]
        scores[name]=max(float(cv2.matchTemplate(target,
            cv2.resize(reference,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST),
            cv2.TM_CCOEFF_NORMED).max()) for scale in (.85,.925,1.,1.075,1.15))
    return scores


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
    evidence=dict(base,border_state=base['state'],label_scores={k:round(v,4) for k,v in labels.items()},
                  geometric_border_support=[round(v,4) for v in border],phase='unknown')
    # Scores are template similarities, not probabilities. Simultaneous strong
    # conflicting labels remain UNKNOWN. Prefix similarity alone never suffices.
    heroes=labels['heroes']>=.78 and labels['all-time']>=.78
    pregame=labels['pregame']>=.74 and labels['pregame']-labels['heroes']>=.08
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
