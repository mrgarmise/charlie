"""In-process arbitration and STOP tests; these are not hardware qualification."""
import threading
from unittest.mock import Mock
import pytest
from experiments.ppal.mobile_navigation import MotionLease, QualifiedMobileExecutor


def setup_executor(clock):
    context=Mock(); context.boot_id='fixture-boot'; context.safe.return_value=True
    context.activation.return_value=({'activation_key':'grant'}, {'direction_envelopes':{'FORWARD':{'max_pwm':35,'max_duration':.1}}})
    context.current={'observation':{'frame':{'id':'frame'},'sensors':{}},
                     'tracking':{'target':{'id':'target'}},'activation':{'activation_key':'grant'}}
    base=Mock(); base.stop_verified.return_value={'sent':True,'acknowledged':True,'physically_stopped':None}
    ex=QualifiedMobileExecutor(base,context,clock=clock)
    lease=MotionLease('supervised_trial',10,'fixture-grant','fixture-boot')
    def request(ident,at):
        return dict(id=ident,at=at,frame_id='frame',action='advance',speed=.15,duration=.1,
                    reasons=[],binding=ex.binding(context.current))
    return ex,base,lease,request


def test_competing_request_rejected_and_stop_preempts_without_waiting():
    now=[1.]; ex,base,lease,request=setup_executor(lambda:now[0])
    entered=threading.Event(); finished=threading.Event(); observed=[]
    def pulse(*args,**kwargs):
        entered.set()
        assert finished.wait(2), 'STOP must not wait for the request lock'
        observed.append(kwargs['cancel'].is_set())
        raise InterruptedError('fixture pulse cancelled')
    base.pulse.side_effect=pulse
    errors=[]
    def run():
        try:ex.execute_bounded(request('first',1.),lease=lease)
        except BaseException as exc:errors.append(exc)
    thread=threading.Thread(target=run);thread.start()
    try:
        assert entered.wait(2)
        with pytest.raises(ValueError,match='another actuator request'):
            ex.execute_bounded(request('second',1.),lease=lease)
        now[0]=1.01
        assert ex.stop()['acknowledged'] is True
        finished.set();thread.join(2)
        assert not thread.is_alive() and observed==[True]
        assert isinstance(errors[0],InterruptedError) and ex.stop_uncertain
        assert base.pulse.call_count==1 and base.stop_verified.call_count==1
    finally:
        finished.set();thread.join(2)


def test_stop_invalidates_old_request_and_rejects_during_stop():
    now=[1.]; ex,base,lease,request=setup_executor(lambda:now[0])
    entered=threading.Event();finished=threading.Event()
    def stop():
        entered.set();assert finished.wait(2)
        return {'sent':True,'acknowledged':True,'physically_stopped':None}
    base.stop_verified.side_effect=stop
    thread=threading.Thread(target=ex.stop);thread.start()
    try:
        assert entered.wait(2)
        with pytest.raises(ValueError,match='STOP'):
            ex.execute_bounded(request('during',1.),lease=lease)
        finished.set();thread.join(2);assert not thread.is_alive()
        now[0]=1.05
        with pytest.raises(ValueError,match='predates STOP'):
            ex.execute_bounded(request('stale',1.),lease=lease)
        base.pulse.assert_not_called()
    finally:
        finished.set();thread.join(2)


def test_executor_direct_admission_rejects_stale_or_unbounded_requests():
    ex,base,lease,request=setup_executor(lambda:1.)
    for change in ({'at':.5},{'speed':.5},{'speed':0},{'duration':.3},{'duration':0},{'id':''},{'reasons':['sensor-fault']}, {'action':'turn','direction':'BAD'}):
        proposal=request('bad',1.);proposal.update(change)
        with pytest.raises(ValueError,match='invalid, stale or vetoed'):
            ex.execute_bounded(proposal,lease=lease)
    base.pulse.assert_not_called()


def test_one_executor_per_transport_and_fault_cannot_be_cleared_by_recreation():
    ex,base,lease,request=setup_executor(lambda:1.)
    with pytest.raises(ValueError,match='already has a qualified executor'):
        QualifiedMobileExecutor(base,ex.context,clock=lambda:1.)
    base.pulse.return_value={'acknowledged':True,'stop':{'sent':None,'acknowledged':False}}
    ex.execute_bounded(request('one',1.),lease=lease)
    assert ex.stop_uncertain
    ex.close()  # Later STOP acknowledgement is not evidence clearing the latch.
    with pytest.raises(ValueError,match='already has a qualified executor'):
        QualifiedMobileExecutor(base,ex.context,clock=lambda:1.)


def test_cleanly_closed_executor_releases_facade_for_new_owner():
    ex,base,lease,request=setup_executor(lambda:1.)
    ex.close()
    next_owner=QualifiedMobileExecutor(base,ex.context,clock=lambda:1.)
    assert next_owner is not ex
    with pytest.raises(ValueError,match='STOP'):
        ex.execute_bounded(request('old',1.1),lease=lease)
