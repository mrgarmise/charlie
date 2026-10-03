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
        if identifier in ('cnn-reconstruction','cnn-classification','cnn-validation-extension'):
            from .cycle import run_plan, gameplay_active
            if gameplay_active(): raise RuntimeError('offline capability unavailable during gameplay')
            objective=(inputs['plan']['candidates'][0]['objective'] if identifier=='cnn-validation-extension' else 'reconstruction' if identifier=='cnn-reconstruction' else 'classification')
            if inputs['dataset'].journal.get(inputs['plan']['dataset_id']).data['payload']['objective']!=objective:
                raise ValueError('method does not match the frozen objective')
            return run_plan(**inputs)
        if identifier in ('model-diagnostics','evidence-review'):
            from .diagnostics import execute
            return execute(**inputs)
        if identifier=='meditation-motion':
            from .meditation import execute
            return execute(**inputs)
        if identifier=='collect-examples':
            from .acquisition import collect_crops
            return collect_crops(**inputs)
        if identifier=='clarify-labels':
            from .acquisition import apply_annotations
            return apply_annotations(**inputs)
        raise ValueError('capability is a prospective evidence request; no acquisition adapter available')


def default_registry():
    registry=CapabilityRegistry()
    for item in (
        Capability('meditation-motion','Generate executable temporal planning candidates from preserved meditation',('meditation-evidence',),('candidate','evidence-gate-result'),.1,('unverified retrospective tracks cannot qualify evaluation','no physical activation adapter'),'fresh independently verified trajectories required'),
        Capability('evidence-review','Search frozen experience references for recurring unresolved questions',('context-evidence',),('retrieval-resolution',),.05,('reported questions are not established causal facts',),'distinct source episodes; unknown provenance abstains'),
        Capability('model-diagnostics','Retrieve discriminating training-history evidence for competing failure explanations',('model-evaluation',),('diagnostic-resolution',),.05,('compatibility is not causal identification','no test pixels are opened'),'frozen training-history predicates'),
        Capability('collect-examples','Retrieve unlabeled recorded candidate crops without a new vision pass',('evidence-gap',),('examples','dataset-request'),.2,('saved subset is biased','replay is not another independent physical experiment'),'hashes and capture/track provenance'),
        Capability('clarify-labels','Seek independent verification of ambiguous interpretations',('uncertainty',),('annotation-request',),.2,('does not certify existing predictions',),'annotation provenance'),
        Capability('cnn-reconstruction','Test whether a compact visual representation generalizes',('RGB-examples','three-independent-groups'),('candidate','heldout-error','opaque-embeddings'),.6,('reconstruction is not semantic recognition or score utility',),'independent held-out reconstruction MSE'),
        Capability('cnn-classification','Test supervised visual recognition',('verified-labels','three-independent-groups'),('candidate','heldout-accuracy'),.6,('weak labels are excluded from validation',),'independent held-out balanced accuracy'),
        Capability('cnn-validation-extension','Compare bounded training duration when retrieved history is still improving',('RGB-examples','model-evaluation'),('validation-comparison','resolved-prediction'),.6,('validation is reused, not fresh independent confirmation','cannot authorize deployment'),'matched configuration, validation only; final test remains sealed'),
    ): registry.register(item)
    return registry
