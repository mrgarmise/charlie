"""Inspectable capability vocabulary, never generated code or authorization."""
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Capability:
    id: str
    purpose: str
    inputs: tuple
    outputs: tuple
    cost: float
    limitations: tuple
    evaluation: str
    execution: str = 'offline'

class CapabilityRegistry:
    def __init__(self): self._items={}
    def register(self, capability):
        if capability.id in self._items: raise ValueError('capability already registered')
        self._items[capability.id]=capability
    def describe(self): return [asdict(c) for c in self._items.values()]
    def get(self, identifier): return self._items[identifier]
    def invoke(self, identifier, *, resources, authorized, **inputs):
        capability=self.get(identifier)
        if identifier not in authorized or set(capability.inputs)-set(resources):
            raise ValueError('available inputs and separate method authorization required')
        if identifier in ('cnn-reconstruction','cnn-classification'):
            from .cycle import run_plan, gameplay_active
            if gameplay_active(): raise RuntimeError('offline capability unavailable during gameplay')
            objective='reconstruction' if identifier=='cnn-reconstruction' else 'classification'
            if inputs['dataset'].journal.get(inputs['plan']['dataset_id']).data['payload']['objective']!=objective:
                raise ValueError('method does not match the frozen objective')
            return run_plan(**inputs)
        raise ValueError('capability is a prospective evidence request; no acquisition adapter available')


def default_registry():
    registry=CapabilityRegistry()
    for item in (
        Capability('collect-examples','Obtain independent examples before fitting a model',('evidence-gap',),('dataset-request',),.2,('requires future observations',),'independent coverage'),
        Capability('clarify-labels','Seek independent verification of ambiguous interpretations',('uncertainty',),('annotation-request',),.2,('does not certify existing predictions',),'annotation provenance'),
        Capability('cnn-reconstruction','Test whether a compact visual representation generalizes',('RGB-examples','three-independent-groups'),('candidate','heldout-error','opaque-embeddings'),.6,('reconstruction is not semantic recognition or score utility',),'independent held-out reconstruction MSE'),
        Capability('cnn-classification','Test supervised visual recognition',('verified-labels','three-independent-groups'),('candidate','heldout-accuracy'),.6,('weak labels are excluded from validation',),'independent held-out balanced accuracy'),
    ): registry.register(item)
    return registry
