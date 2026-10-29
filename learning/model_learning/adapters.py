"""Trusted task adapters. Models cannot register code or choose import paths."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PerceptionTask:
    task: str
    labels: tuple
    preprocessing: str
    runtime: str
    implementation_file: str
    incumbent_file: str
    frame: object
    features: object
    predict: object
    incumbent: object


def get_adapter(task='robotron.screen_state'):
    if task!='robotron.screen_state':raise ValueError('training task adapter not registered: '+str(task))
    from . import robotron
    return PerceptionTask(task,robotron.SCREEN_STATE_LABELS,robotron.PREPROCESSING,'numpy-cpu-json-v1',
        robotron.__file__,robotron.INCUMBENT_FILE,robotron.frame,robotron.features,robotron.predict,robotron.incumbent)
