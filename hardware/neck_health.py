"""Lightweight existing-observation checks, not an optimizer or fault diagnosis."""
import math
from .neck_calibration import CalibrationJournal


class NeckHealth:
    def __init__(self,controller,profile_id,evidence,*,repository=None,journal=None,
                 min_response=.05,max_response=200,unexpected_shift=20,persistence=3,response_model=None):
        self.controller,self.profile_id,self.evidence=controller,profile_id,evidence
        self.repository,self.journal=repository,journal
        self.minimum,self.maximum=min_response,max_response
        self.shift,self.persistence=unexpected_shift,persistence
        self.pending=None;self.previous=None;self.unexpected=0;self.quarantined=False
        self.failures=0
        self.response_model=response_model

    def record(self,decision,**details):
        event=dict(category='neck_health',profile_id=self.profile_id,decision=decision,
                   mechanical_fault_confirmed=False,**details)
        if hasattr(self.evidence,'append'): self.evidence.append(event)
        else: self.evidence(event)
        return event

    def prepare(self,previous_pose,target_pose,corners):
        if self.quarantined: raise PermissionError('supervised recalibration required')
        if self.pending is not None: raise PermissionError('unverified movement; no retry')
        self.pending=dict(previous_pose=list(previous_pose),requested_pose=list(target_pose),
                          previous_corners=corners)
        self.record('movement prepared',**self.pending)

    def unsafe(self,reason,**details):
        self.quarantined=True;self.failures+=1
        try:
            report=self.record('safety uncertain; request supervised recalibration',reason=reason,
                alternatives=['target occlusion','scene transition','focus/exposure change',
                          'camera mount movement','servo/power/wiring or mechanical degradation'],
            physical_authorization=False,passive_allowed=True,digital_only_allowed=True,
                unsuccessful_movements=self.failures,**details)
        finally:
            # Stop even if diagnostic persistence fails.
            try:
                if hasattr(self.controller,'neck_uncertain'): self.controller.neck_uncertain()
            finally: self.controller.stop()
        if self.repository: self.repository.quarantine(self.profile_id,reason,report)
        return report

    @staticmethod
    def valid(corners):
        try:
            return (isinstance(corners,(list,tuple)) and len(corners)==4 and
                all(isinstance(p,(list,tuple)) and len(p)==2 and
                    all(math.isfinite(float(v)) for v in p) for p in corners))
        except (ValueError,TypeError,OverflowError):return False

    def observe(self,corners,*,telemetry=None,expected_transition=False):
        if self.quarantined: return self.record('passive only; profile quarantined')
        if self.pending is not None:
            pending=self.pending;self.pending=None
            if (not self.valid(corners) or not self.valid(pending['previous_corners'])
                    or not telemetry or telemetry.get('moving') or telemetry.get('profile_invalid')):
                return self.unsafe('movement evidence unavailable or inconsistent',command=pending)
            import numpy as np
            delta=float(np.mean(np.linalg.norm(np.asarray(corners)-np.asarray(pending['previous_corners']),axis=1)))
            degrees=sum(abs(a-b) for a,b in zip(pending['previous_pose'],pending['requested_pose']))
            commanded=[telemetry.get('pan'),telemetry.get('tilt')]
            # JSON telemetry must contain finite numeric position estimates.
            # NaN comparisons are false and otherwise silently admit uncertainty.
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in commanded):
                return self.unsafe('invalid commanded position telemetry',command=pending,
                                   reported_positions=[repr(v) for v in commanded])
            if (any(abs(a-b)>.05 for a,b in zip(commanded,pending['requested_pose']))
                    or delta<self.minimum*degrees or delta>self.maximum*degrees):
                return self.unsafe('command-to-view discrepancy',visual_displacement=delta,command=pending,
                                   telemetry=telemetry)
            if self.response_model is not None:
                actual=np.mean(np.asarray(corners)-np.asarray(pending['previous_corners']),axis=0)
                angular=np.asarray(pending['requested_pose'])-np.asarray(pending['previous_pose'])
                predicted=np.asarray(self.response_model['pan'])*angular[0]+np.asarray(self.response_model['tilt'])*angular[1]
                if np.linalg.norm(actual-predicted)>max(.5,np.linalg.norm(predicted)*.75):
                    return self.unsafe('visual direction or magnitude disagrees with calibration',
                                       predicted=predicted.tolist(),observed=actual.tolist(),command=pending)
            self.record('movement visually supported; not measured servo position',visual_displacement=delta,
                        command=pending,telemetry=telemetry)
        elif expected_transition:
            self.unexpected=0
        elif self.valid(corners) and self.valid(self.previous):
            import numpy as np
            delta=float(np.max(np.linalg.norm(np.asarray(corners)-np.asarray(self.previous),axis=1)))
            self.unexpected=self.unexpected+1 if delta>self.shift else 0
            if self.unexpected>=self.persistence:
                return self.unsafe('persistent unexpected viewpoint change',visual_displacement=delta)
        if self.valid(corners):
            if self.unexpected==0:self.previous=corners
        return self.record('observation accepted',visual_tracking_available=self.valid(corners))

    def executive_context(self):
        return dict(category='neck_health',profile_id=self.profile_id,status='quarantined' if self.quarantined else 'monitoring',
                    physical_authorization=False,resources=['passive_observation','digital_correction'],
                    requested_project='supervised_neck_recalibration' if self.quarantined else None,
                    autonomous_retries_allowed=False,mechanical_fault_confirmed=False)

    def reflect_to_executive(self,executive,journal):
        """Use existing Reflection/Executive evidence gates; no physical grant."""
        from memory.learning_projects import reflect_project_opportunities
        context=self.executive_context()
        if not self.quarantined:return []
        episode='neck-health:'+self.profile_id
        source=journal.append('observation',context,episode=episode,producer='NeckHealth',version='1')
        hypothesis=dict(method='supervised_neck_recalibration',scope=dict(profile_id=self.profile_id),
            expected='independently verified clearance and command-to-view agreement',
            conditions=[dict(supervised=True),dict(supervised=False)],
            observed_conditions=[dict(supervised=False)],evidence_ids=[source.id],
            requires=['physical_authorization','supervision','electrical_clearance'])
        proposals=reflect_project_opportunities(journal,episode,[hypothesis])
        return [executive.propose(p['proposal'],journal,[p['evidence_id']]) for p in proposals]
