"""Exact PR #14 gateway compatibility; all approval performance is SIMULATED."""
import importlib.util
import os
import sys
import pytest
from test_model_learning import setup,corpus,controlled_qualification,REPO
from learning.model_learning.robotron import import_fixtures
from learning.model_learning.human import ModelHumanGateway
from learning.deployment import CapabilityDeployment


def gateway_module():
    path=os.environ.get('CHARLIE_MODEL_LEARNING_SHARED_GATEWAY')
    if not path:pytest.skip('exact PR #14 gateway not supplied; dedicated CI supplies it')
    spec=importlib.util.spec_from_file_location('memory.model_learning_gateway_compat',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module


def test_async_label_reply_remains_fallible_pending_review(setup):
    module=gateway_module();service,e,_=setup;import_fixtures(service.data,REPO)
    e.consider_model_learning(service)
    gateway=module.HumanInteractionGateway(service.journal)
    adapter=ModelHumanGateway(service,gateway,need_type=module.InformationNeed)
    dispatch=adapter.dispatch();assert dispatch[0]['asked']
    question=dispatch[0]['question_id']
    gateway.answer(question,value='unknown',operator='controlled-human',request_id='label-answer-test')
    reviews=adapter.receive()
    assert len(reviews)==1 and reviews[0].data['payload']['status']=='pending_independent_review'
    assert len(service.data.events('model_label'))==5
    assert adapter.receive()==[] and service.active() is None


def test_async_explicit_approval_review_and_shadow_activation(setup,tmp_path):
    module=gateway_module();service,e,_=setup;corpus(service,tmp_path)
    result=e.consider_model_learning(service)
    controlled_qualification(service,result['candidate_id'])
    gateway=module.HumanInteractionGateway(service.journal)
    adapter=ModelHumanGateway(service,gateway,need_type=module.InformationNeed)
    question=adapter.dispatch()[0]['question_id']
    answer=gateway.answer(question,value='approve_shadow',operator='controlled-human',request_id='approval-answer-test')
    assert service.active() is None
    grant=adapter.review_approval(answer.id,reviewer='controlled-reviewer',reason='SIMULATED qualification transaction test')
    assert adapter.review_approval(answer.id,reviewer='controlled-reviewer',reason='same explicit review').id==grant.id
    CapabilityDeployment(service.journal).activate_perception_shadow(service,grant.id)
    assert service.active()['mode']=='shadow'
    assert service.active()['physical_authorization'] is False
