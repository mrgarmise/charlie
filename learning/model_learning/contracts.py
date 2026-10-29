"""Versioned declarative contracts; all artifacts are data, never executable code."""
from dataclasses import dataclass, asdict
import math

VERSION = 'model-learning-v1'

@dataclass(frozen=True)
class LearningNeed:
    task: str
    reason: str
    evidence_ids: tuple
    desired_outcome: str = 'held-out macro recall >= 0.9 with unknown abstention'
    priority: float = .5
    max_candidates: int = 1

    def __post_init__(self):
        if not self.task or not self.reason or not self.evidence_ids or not 0 <= self.priority <= 1 or self.max_candidates != 1:
            raise ValueError('bounded evidence-backed need required')

@dataclass(frozen=True)
class DatasetCandidate:
    task: str
    rows: tuple
    labels: tuple
    version: str = VERSION
    retention: str = 'local until explicit operator purge; never publish private pixels'

@dataclass(frozen=True)
class TrainingProposal:
    need_id: str
    dataset_id: str
    algorithm: str = 'nearest-centroid-v1'
    wall_seconds: float = 10.
    cpu_seconds: int = 5
    memory_mb: int = 512
    disk_mb: int = 16
    max_frames: int = 256

    def __post_init__(self):
        if self.algorithm != 'nearest-centroid-v1' or not self.need_id or not self.dataset_id:
            raise ValueError('registered algorithm and lineage required')
        if not math.isfinite(self.wall_seconds) or not .1 <= self.wall_seconds <= 60:
            raise ValueError('bounded wall budget required')
        for name, low, high in [('cpu_seconds',1,30),('memory_mb',128,2048),('disk_mb',1,64),('max_frames',3,1024)]:
            value=getattr(self,name)
            if type(value) is not int or not low<=value<=high: raise ValueError('invalid '+name)

@dataclass(frozen=True)
class ModelCandidate:
    artifact: str
    sha256: str
    dataset_id: str
    proposal_id: str
    labels: tuple
    preprocessing: str = 'rgb-spatial-16x12-v1'
    runtime: str = 'numpy-cpu-json-v1'
    mode: str = 'shadow'
    implementation_sha256: str = ''

@dataclass(frozen=True)
class QualificationDecision:
    candidate_id: str
    evaluation_id: str
    accepted: bool
    reasons: tuple
    approval: str = 'required'


def document(value):
    return dict(schema=VERSION, **asdict(value))
