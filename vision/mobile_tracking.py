"""Conservative temporal pet association; track IDs are NOT pet identities."""
from dataclasses import dataclass
import math
from uuid import uuid4


@dataclass
class Track:
    id: str
    label: str
    box: tuple
    confidence: float
    at: float
    hits: int = 1
    observed: bool = True
    ambiguous: bool = False


def iou(a,b):
    area=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return area/((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-area)


class PetTracker:
    def __init__(self, *, min_score=.6, confirmations=2, loss_seconds=1., categories=('cat','dog')):
        if (not 0<min_score<=1 or type(confirmations) is not int or confirmations<1
                or not 0<loss_seconds<=5 or not set(categories)<= {'cat','dog','person','human_face','unknown'}):
            raise ValueError('invalid tracker configuration')
        self.min_score,self.confirmations,self.loss_seconds=min_score,confirmations,loss_seconds
        self.categories=set(categories)
        self.tracks={}
        self.selected=None
        self.last_at=None
        self.session=uuid4().hex
        self.counter=0

    def update(self, packet):
        at=packet['frame']['received_at']
        if not math.isfinite(at) or (self.last_at is not None and at<=self.last_at): raise ValueError('reordered track update')
        self.last_at=at
        self.tracks={k:t for k,t in self.tracks.items() if at-t.at<=self.loss_seconds}
        for t in self.tracks.values(): t.observed=False; t.ambiguous=False
        rows=[r for r in packet['objects'] if r['label'] in self.categories and r['confidence']>=self.min_score]
        if len(rows)>128: raise ValueError('too many objects')
        matches={}
        for index,row in enumerate(rows):
            candidates=sorted([(iou(row['box'],t.box),t.id) for t in self.tracks.values() if t.label==row['label']],reverse=True)
            candidates=[c for c in candidates if c[0]>=.15]
            if candidates and (len(candidates)==1 or candidates[0][0]-candidates[1][0]>.15):
                matches[index]=candidates[0][1]
            elif candidates:
                for _,key in candidates:self.tracks[key].ambiguous=True
                matches[index]=None  # ambiguous crossing abstains, doesn't invent identity
        contested={key for key in matches.values() if key is not None and list(matches.values()).count(key)>1}
        for key in contested:self.tracks[key].ambiguous=True
        for index,row in enumerate(rows):
            if index in matches:
                key=matches[index]
                if key is None or key in contested or self.tracks[key].ambiguous:continue
                t=self.tracks[key]
                t.box=tuple(row['box']); t.confidence=row['confidence']; t.at=at; t.hits+=1; t.observed=True
            else:
                self.counter+=1
                key=f'{self.session}:{self.counter}'
                self.tracks[key]=Track(key,row['label'],tuple(row['box']),row['confidence'],at)
        candidates=[t for t in self.tracks.values() if t.observed and not t.ambiguous and t.hits>=self.confirmations]
        target=next((t for t in candidates if t.id==self.selected),None)
        # Hold a recently occluded target; do not switch to another animal immediately.
        if target is None and (self.selected is None or self.selected not in self.tracks):
            target=max(candidates,key=lambda t:(t.confidence,(t.box[2]-t.box[0])*(t.box[3]-t.box[1]),t.id),default=None)
        self.selected=target.id if target else (self.selected if self.selected in self.tracks else None)
        from dataclasses import asdict
        return dict(target=asdict(target) if target else None, tracks=[asdict(t) for t in self.tracks.values()],
                    species_only=True, individual_pet_identity='unverified', target_lost=target is None)


def emit_attention(bus, tracking, frame, *, enable_legacy=False):
    """Rich event by default. Legacy 2D bridging requires separate caller choice.

    Existing AttentionManager consumes legacy events and can move hardware, so
    unarmed pet mode NEVER emits them. No change to existing face selection.
    """
    bus.emit('mobile_observation', tracking)
    if not enable_legacy:return
    target=tracking['target']
    if target is None:bus.emit('vision_lost'); return
    x,y,r,b=target['box']
    # Existing vision events use main-camera 1280x720 coordinates.
    w,h=frame['geometry']
    bus.emit('vision_target', ((x+r)/2/w*1280,(y+b)/2/h*720))
