"""Compatibility against an exact PR #13 bus file; no stack merge or hardware."""
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
from memory.evidence import EvidenceJournal
from learning.model_learning.data import DatasetStore
from learning.model_learning.subscriber import RegisteredShadowPerception


def test_registered_subscription_preserves_other_subscriber(tmp_path,monkeypatch):
    path=os.environ.get('CHARLIE_MODEL_LEARNING_SHARED_BUS')
    if not path:pytest.skip('exact PR #13 bus source not supplied; dedicated CI supplies it')
    spec=importlib.util.spec_from_file_location('model_learning_shared_bus',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    bus=module.StimulusBus();owner=object();clock=lambda:1.
    bus.claim_observations('camera/bookmarks',owner,metadata={'modality':'evidence-bookmark'})
    existing=bus.subscribe_observations('camera/bookmarks',max_age=.25,clock=clock)
    journal=EvidenceJournal(tmp_path/'notebook.sqlite3');data=DatasetStore(journal,tmp_path/'pixels')
    try:
        original=Path(__file__).resolve().parent/'fixtures/robotron-screen-states/terminal.jpg'
        row=data.add(original,session='controlled-bookmark',provenance=dict(source='camera/bookmarks',generation='g'),authentic=True)
        fake=SimpleNamespace(journal=journal,adapter=SimpleNamespace(task='robotron.screen_state'))
        # Candidate generation tested in the independent real-worker tests.
        class Consumer:
            def __init__(self,*args):pass
            def consume(self,identifier):return dict(status='shadow',prediction=dict(label='terminal',mode='shadow'))
        monkeypatch.setattr('learning.model_learning.subscriber.ShadowSubscriber',Consumer)
        adapter=RegisteredShadowPerception(bus,fake,'controlled',bookmark_source='camera/bookmarks',output_source='perception/model-shadow',observation_type=module.Observation,clock=clock)
        output=bus.subscribe_observations('perception/model-shadow',max_age=.25,clock=clock)
        for sequence,generation in [(1,'g'),(2,'wrong-generation')]:
            observation=module.Observation(source='camera/bookmarks',sequence=sequence,received_at=1.,values=dict(observation_id=row.id),provenance={},generation=generation)
            bus.publish_observation('camera/bookmarks',owner,observation)
            result=adapter.poll()
            assert result['prediction']['label']==('terminal' if generation=='g' else 'unknown')
            assert existing.read().values['observation_id']==row.id
            assert output.read().provenance['authority']=='none'
        adapter.close()
        assert bus.observation_owners['camera/bookmarks'] is owner
    finally:journal.close()
