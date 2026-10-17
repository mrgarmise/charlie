"""Conservative, class-free shot-origin evidence. No actuator or camera access.

Thresholds are geometric gates, not probabilities. Native qualification remains
required before selecting this alternative confirmation route in a campaign.
"""
import math
from .eyes.detectors import Detection


def candidates(frame):
    """One native connected-component pass; no template scoring or crop copies."""
    import cv2
    import numpy as np
    rgb = np.asarray(frame.convert('RGB'))
    background = cv2.blur(rgb, (31, 31))
    contrast = (rgb.astype(np.int16)-background.astype(np.int16)).max(axis=2)
    mask = ((rgb.max(axis=2)>145) & (contrast>45)).astype('uint8')
    mask[:5]=0; mask[-5:]=0; mask[:,:5]=0; mask[:,-5:]=0
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    height, width = mask.shape
    if len(stats)>257:return [], [] # bound association cost in transition/noise fields
    bodies, points = [], []
    for x,y,w,h,area in stats[1:]:
        p=((x+w/2)/width*100, (y+h/2)/height*100)
        if 2 <= area and w/width*100 <= 1.8 and h/height*100 <= 2.5:
            points.append(p)
        elif area>=8 and 3<=w<width*.4 and 3<=h<height*.4:
            bodies.append((Detection('unknown',p,tuple(map(int,(x,y,x+w,y+h))),int(area)),{}))
    return bodies, points


class ShotOrigins:
    def __init__(self):
        self.reset()

    def reset(self):
        self.window=None
        self.previous=[]
        self.paths=[]
        self.votes={}
        self.confirmed=None

    def begin(self, direction, execution, bodies, baseline):
        """Only acknowledged command timing may open an evidence window."""
        self.window=None; self.paths=[]; self.previous=list(baseline)
        if not isinstance(execution,dict) or execution.get('move')!='STAY':return False
        vectors={'E':(1,0),'W':(-1,0),'N':(0,-1),'S':(0,1),
                 'NE':(1,-1),'NW':(-1,-1),'SE':(1,1),'SW':(-1,1)}
        if vectors.get(execution.get('fire'))!=tuple(direction):return False
        ready=execution.get('controls_ready_at'); end=execution.get('pulse_finished_at')
        if ready is None or end is None or not math.isfinite(ready+end) or end<ready:
            return False
        n=math.hypot(*direction)
        if not n:return False
        if any(ready-vote['start']>3. for votes in self.votes.values() for vote in votes):
            self.votes.clear();self.confirmed=None
        self.window=dict(direction=tuple(v/n for v in direction),start=ready,end=end,
                         bodies=dict(bodies),command=len(self.votes))
        return True

    def observe(self, points, at):
        evidence=[]; w=self.window
        if w is None:return evidence
        if not math.isfinite(at) or at<=w['start'] or at>w['end']+.75:
            self.window=None; return evidence
        if len(points)>64: # merged transition/effect field, no identity inference
            self.window=None; return evidence
        # Unique bidirectional nearest association. Ambiguous crossings are dropped.
        paths=[]
        for p in points:
            matches=[path for path in self.paths if math.dist(path[-1][1],p)<8]
            if len(matches)==1:
                path=matches[0]
                if sum(math.dist(path[-1][1],q)<8 for q in points)!=1:continue
                if at<=path[-1][0]:continue
                path=path+[(at,tuple(p))]
            elif not matches and not any(math.dist(p,q)<2 for q in self.previous):
                path=[(at,tuple(p))]
            else:continue
            paths.append(path)
            if len(path)!=3:continue
            t0,a=path[0]; t1,b=path[-1]; dt=t1-t0
            v=((b[0]-a[0])/dt,(b[1]-a[1])/dt); speed=math.hypot(*v)
            if speed<2 or sum(v[i]*w['direction'][i] for i in (0,1))/speed<.97:continue
            if any(math.dist(q,tuple(a[i]+v[i]*(t-t0) for i in (0,1)))>.5 for t,q in path):continue
            origins=[]
            for key,body in w['bodies'].items():
                travel=sum((a[i]-body[i])*v[i] for i in (0,1))/speed**2
                emission=t0-travel
                residual=math.dist(body,tuple(a[i]-v[i]*travel for i in (0,1)))
                if travel>=0 and w['start']-1e-9<=emission<=w['end']+.15 and residual<=1.5:
                    origins.append((key,emission))
            if len(origins)!=1:continue
            key,emission=origins[0]
            vote=dict(track_id=key,direction=w['direction'],origin=list(w['bodies'][key]),
                      emission_at=emission,observations=path,source='command_aligned_outward_trajectory')
            # At most one vote per command per origin; shot counts are not FPS.
            prior=self.votes.setdefault(key,[])
            if not any(x['start']==w['start'] for x in prior):
                prior.append(dict(vote,start=w['start']))
                evidence.append(vote)
        self.paths=paths;self.previous=list(points)
        qualified=[]
        for key,votes in self.votes.items():
            if any(abs(a['direction'][0]*b['direction'][1]-a['direction'][1]*b['direction'][0])>.7
                   and math.dist(a['origin'],b['origin'])<=2
                   for a in votes for b in votes):qualified.append(key)
        self.confirmed=qualified[0] if len(qualified)==1 and len(self.votes)==1 else None
        return evidence


def timing_summary(rows):
    """Separate sensor cadence from independently delivered observations."""
    from statistics import median
    captures=[r.get('capture') or {} for r in rows]
    stamps=[r.get('capture_timestamp') for r in rows]
    gaps=[b-a for a,b in zip(stamps,stamps[1:]) if a is not None and b is not None and b>a]
    def med(key):
        vals=[c[key] for c in captures if isinstance(c.get(key),(int,float)) and c[key]>0]
        return median(vals) if vals else None
    duration=med('frame_duration_us')
    executions=list({e.get('started_at'):e for r in rows
        if isinstance((e:=r.get('control_execution')),dict) and e.get('started_at') is not None}.values())
    acknowledgments=[c['ack_at']-c['sent_at'] for e in executions for c in e.get('commands',[])
                     if c.get('ack_at') is not None and c.get('sent_at') is not None]
    latency=[e['controls_ready_at']-e['started_at'] for e in executions
             if e.get('controls_ready_at') is not None and e.get('started_at') is not None]
    return dict(independent_observation_hz=1/median(gaps) if gaps else None,
                sensor_frame_duration_us=duration, sensor_cadence_hz=1e6/duration if duration else None,
                exposure_us=med('exposure_time_us'),capture_seconds=med('capture_seconds'),
                controller_ready_seconds=median(latency) if latency else None,
                controller_command_ack_seconds=median(acknowledgments) if acknowledgments else None,
                unique_controller_executions=len(executions),
                processing_seconds=median([r['acquisition_processing_seconds'] for r in rows
                    if isinstance(r.get('acquisition_processing_seconds'),(int,float))]) if any(isinstance(r.get('acquisition_processing_seconds'),(int,float)) for r in rows) else None,
                caveat='delivered observations may skip sensor frames; no projectile rate inferred')


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    ap=argparse.ArgumentParser(description='Read-only timing audit of recorded agency JSONL')
    ap.add_argument('agency_jsonl',type=Path)
    args=ap.parse_args()
    print(json.dumps(timing_summary([json.loads(line) for line in args.agency_jsonl.read_text().splitlines()]),indent=2))
