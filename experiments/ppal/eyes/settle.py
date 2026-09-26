"""Find Robotron's colored rectangular border anew for each recording."""
import json
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import ImageDraw
from .calibration import Calibration


def locate(frame):
    rgb = np.asarray(frame.convert('RGB'))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    height, width = rgb.shape[:2]
    mask = ((hsv[:,:,1] > 10) & (hsv[:,:,2] > 155)).astype(np.uint8)*255
    lines = cv2.HoughLinesP(mask, 1, np.pi/180, 100,
                           minLineLength=min(width,height)*.35, maxLineGap=30)
    if lines is None:
        raise ValueError('No game border found; show active Robotron and all four corners')
    groups = [[], []]
    for x1,y1,x2,y2 in lines.reshape(-1,4):
        dx,dy = float(x2-x1),float(y2-y1)
        if abs(dy) < .25*abs(dx):
            group=0; position=(y1+y2)/2
        elif abs(dx) < .35*abs(dy):
            group=1; position=(x1+x2)/2
        else:
            continue
        length=float(np.hypot(dx,dy))
        line=np.cross([x1,y1,1.],[x2,y2,1.])
        groups[group].append((length,position,line))
    selected=[]
    for group in groups:
        kept=[]
        for item in sorted(group,key=lambda x:x[0],reverse=True):
            if all(abs(item[1]-other[1])>12 for other in kept):
                kept.append(item)
            if len(kept)==8:
                break
        selected.append(sorted(kept,key=lambda x:x[1]))
    from itertools import combinations
    candidates=[]
    for top,bottom in combinations(selected[0],2):
        for left,right in combinations(selected[1],2):
            corners=[]
            for h,v in ((top,left),(top,right),(bottom,right),(bottom,left)):
                intersection=np.cross(h[2],v[2])
                corners.append(intersection[:2]/intersection[2])
            points=np.array(corners)
            if (not np.all(np.isfinite(points)) or np.any(points[:,0]<3)
                or np.any(points[:,0]>width-4) or np.any(points[:,1]<3)
                or np.any(points[:,1]>height-4)):
                continue
            area=cv2.contourArea(points.astype(np.float32))
            if not .15*width*height<area<.90*width*height:
                continue
            support=[]
            colors=[]
            for start,end in zip(points,np.roll(points,-1,axis=0)):
                samples=np.linspace(start,end,100).astype(int)
                normal=np.array([-(end-start)[1],(end-start)[0]])
                normal=normal/max(np.linalg.norm(normal),1)*9
                hits=[]
                edge_colors=[]
                for x,y in samples:
                    sides=[np.array([x,y])+normal,np.array([x,y])-normal]
                    if any(not (0<=q[0]<width and 0<=q[1]<height) for q in sides):
                        hits.append(False); continue
                    patch=rgb[y-2:y+3,x-2:x+3].reshape(-1,3)
                    pixel=patch[np.argmax(patch.max(axis=1))].astype(float)
                    edge_colors.append(pixel/max(float(pixel.sum()),1))
                    peak=float(hsv[y-2:y+3,x-2:x+3,2].max())
                    side_values=[float(hsv[int(q[1]),int(q[0]),2]) for q in sides]
                    hits.append(bool(mask[y-2:y+3,x-2:x+3].any()) and peak-max(side_values)>35)
                support.append(np.mean(hits))
                colors.append(np.median(edge_colors,axis=0))
            if min(support)<.65:
                continue
            if np.max(np.linalg.norm(np.array(colors)-np.median(colors,axis=0),axis=1))>.10:
                continue
            candidates.append((min(support),points))
    if not candidates:
        raise ValueError('No complete game border found; include all corners and aim more squarely at TV')
    candidates.sort(key=lambda item:item[0],reverse=True)
    return candidates[0][1]


def prepare(source, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    print('Settling camera exposure/autofocus, then locating the game border...')
    start = time.monotonic()
    for _ in range(90):
        source.read()
        if time.monotonic()-start >= 2:
            break
    observations = []
    frame = None
    try:
        for _ in range(12):
            frame = source.read()
            observations.append(locate(frame))
            time.sleep(.1)
        corners = np.median(observations,axis=0)
        jitter = float(np.max(np.linalg.norm(np.array(observations)-corners,axis=2)))
        if jitter > 6:
            raise ValueError(f'Camera view still moving ({jitter:.1f}px); let it settle and retry')
        calibration = Calibration.from_pixels(corners.tolist(),frame.size)
        calibration.save(output/'calibration.json')
        frame.save(output/'setup-raw.png')
        preview = frame.copy()
        ImageDraw.Draw(preview).line([tuple(p) for p in corners]+[tuple(corners[0])],fill='lime',width=3)
        preview.save(output/'setup-border.png')
        calibration.apply(frame).save(output/'setup-playfield.png')
        (output/'setup.json').write_text(json.dumps({'status':'border stable', 'max_jitter_pixels':jitter,
            'note':'Geometry check only; does not certify focus, exposure, or object recognition.'},indent=2)+'\n')
        print(f'New screen calibration saved; border jitter {jitter:.1f}px')
        return calibration
    except ValueError as exc:
        if frame is not None:
            frame.save(output/'setup-failed.png')
        (output/'setup.json').write_text(json.dumps({'status':'failed','reason':str(exc)},indent=2)+'\n')
        raise
