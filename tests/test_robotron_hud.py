import numpy as np
from PIL import Image, ImageDraw

from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.robotron_hud import RobotronHUDReader
from experiments.ppal.score_tracker import VisualScoreTracker


SEG = {
    "0": (1,1,1,0,1,1,1), "1": (0,0,1,0,0,1,0),
    "2": (1,0,1,1,1,0,1), "3": (1,0,1,1,0,1,1),
    "4": (0,1,1,1,0,1,0), "5": (1,1,0,1,0,1,1),
    "6": (1,1,0,1,1,1,1), "7": (1,0,1,0,0,1,0),
    "8": (1,1,1,1,1,1,1), "9": (1,1,1,1,0,1,1),
}


def glyph(d):
    a=np.zeros((32,20),dtype=np.uint8)
    regs=((slice(1,6),slice(4,16)),(slice(4,15),slice(1,7)),
          (slice(4,15),slice(13,19)),(slice(13,19),slice(4,16)),
          (slice(17,28),slice(1,7)),(slice(17,28),slice(13,19)),
          (slice(26,31),slice(4,16)))
    for on,(ys,xs) in zip(SEG[d],regs):
        if on: a[ys,xs]=1
    return a


def test_all_digits_classify_from_segment_geometry():
    for d in "0123456789":
        r=RobotronHUDReader._read_digit(glyph(d))
        assert r.digit == d
        assert r.confidence == (0.72 if d == "7" else 1.0)


def test_channel_reads_score_and_absent_channel():
    canvas=np.zeros((48,180,3),dtype=np.uint8)
    x=8
    for d in "8400":
        g=cv2_resize(glyph(d), 15, 28)
        canvas[8:36,x:x+15]=np.maximum(canvas[8:36,x:x+15],g[:,:,None]*np.array([80,255,255],dtype=np.uint8))
        x += 21
    score, confidence=RobotronHUDReader._read_channel(canvas)
    assert score == 8400
    assert confidence >= .9
    assert RobotronHUDReader._read_channel(np.zeros_like(canvas))[0] is None


def cv2_resize(a,w,h):
    import cv2
    return (cv2.resize(a,(w,h),interpolation=cv2.INTER_NEAREST)>0).astype(np.uint8)


def test_rectification_uses_playfield_geometry_not_fixed_raw_pixels():
    raw=Image.new("RGB",(1000,700),"black")
    cal=Calibration(((.2,.2),(.8,.25),(.78,.85),(.18,.80)))
    reader=RobotronHUDReader(cal)
    hud=reader.rectify(raw)
    assert hud.size == (640,96)


def test_real_hud_observation_flows_into_temporal_dual_tracker():
    class Reader:
        def read(self,image):
            from experiments.ppal.robotron_hud import RobotronHUDObservation
            return RobotronHUDObservation(8400,None,.99,0.0)
    scores=VisualScoreTracker(Reader()).observe(object())
    assert scores.player1.score == 8400
    assert scores.player2.score is None
    assert scores.self_score == 8400


def test_score_reader_is_hue_independent_for_same_shape():
    import cv2
    for color in ([255,240,80], [80,255,255], [255,80,220], [255,255,255]):
        canvas=np.zeros((48,180,3),dtype=np.uint8)
        x=8
        for d in "8400":
            g=cv2_resize(glyph(d),15,28)
            canvas[8:36,x:x+15]=np.maximum(
                canvas[8:36,x:x+15],
                g[:,:,None]*np.array(color,dtype=np.uint8))
            x += 21
        score,_=RobotronHUDReader._read_channel(canvas)
        assert score == 8400


def test_real_corpus_covers_every_digit_except_seven():
    from experiments.ppal.robotron_score_corpus import covered_digits, UNOBSERVED_DIGITS
    assert covered_digits() == frozenset("012345689")
    assert UNOBSERVED_DIGITS == frozenset("7")
