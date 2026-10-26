"""One unarmed sensing step in Charlie's existing behavior namespace."""
from experiments.ppal.mobile_navigation import MobileNavigator, MobileExecutionGate
from vision.mobile_tracking import PetTracker, emit_attention


class MobileObserveBehavior:
    def __init__(self, source, perception, evidence, *, tracker=None, navigator=None, gate=None, bus=None):
        self.source,self.perception,self.evidence=source,perception,evidence
        self.tracker=tracker or PetTracker()
        self.navigator=navigator or MobileNavigator(clock=perception.clock)
        self.gate=gate or MobileExecutionGate(clock=perception.clock)
        self.bus=bus
        self.retention=None
        self.attention=None;self.context=None;self.executor=None;self.base=None
        if hasattr(source,'on_fault'):source.on_fault=self.acquisition_fault
        if self.gate.backend is not None:raise ValueError('observation behavior has no physical execution backend')

    def acquisition_fault(self, error, metrics=None):
        self.tracker.invalidate(type(error).__name__)
        self.gate.close()
        if self.context is not None:self.context.current=None
        for model in (self.perception.detector,self.perception.depth):
            if hasattr(model,'close'):model.close()
        self.evidence.fault(error,metrics)
        if self.bus is not None:self.bus.emit('mobile_observation',dict(target=None,target_lost=True,reason='acquisition_fault'))

    def step(self):
        try:
            frame=self.source.read()
            observation=self.perception.observe(frame)
            if observation is None:return None
            tracking=self.tracker.update(observation)
            if self.context is not None:
                observation=self.context.bind(observation,tracking)
                if self.context.current is not None:
                    from experiments.ppal.mobile_navigation import MobileLimits
                    envelope=self.context.current['report']['envelope']
                    self.navigator.limits=MobileLimits(stand_off_m=envelope['stand_off_m']+envelope['margin_m'],
                        max_duration=min(.2,envelope['max_duration']))
            proposal=self.navigator.propose(observation,tracking,observation['sensors'])
            execution=(dict(dispatched=False,approved=False,rejected=['awaiting_attention'],executed=None)
                       if self.attention is not None else self.gate.execute(proposal))
            if self.retention is not None:
                artifact=self.retention(frame,observation,tracking)
                if artifact is not None:observation['frame']['artifact']=artifact
            row=self.evidence.record(observation,tracking,proposal,execution)
            if hasattr(self,'before_attention'):self.before_attention()
            self.evidence.opportunities(row.id)
            if self.bus is not None:emit_attention(self.bus,tracking,observation['frame'])
            result=dict(observation=observation,tracking=tracking,proposal=proposal,execution=execution,evidence_id=row.id)
            if self.attention is not None:
                self.bus.emit('mobile_opportunity',result)
                self.attention.update(None)
            return result
        except StopIteration:
            self.gate.close()
            raise
        except BaseException as exc:
            self.acquisition_fault(exc)
            raise

    def close(self):
        try:self.gate.close()
        finally:
            try:
                if self.base is not None:
                    try:self.executor.close() if self.executor is not None else self.base.close()
                    finally:self.base=None
            finally:
                try:self.source.close()
                finally:
                    for model in (self.perception.detector,self.perception.depth):
                        if hasattr(model,'close'):model.close()

    def bind_attention(self,attention,executive,registry,*,context=None,base_factory=None):
        self.attention=attention;self.context=context;self.base_factory=base_factory
        self.executive_resources=set();self.last_decision=None;self.last_attention_key=None;self.decision_at=None
        self.last_execution=None;self.intent='observe';self.executor=None;self.base=None
        attention.attach_pet_service(self,executive,registry)

    def readiness(self):
        follow_reasons=[]
        if getattr(self,'context',None) is None:follow_reasons.append('no active physical qualification/telemetry')
        else:
            try:
                self.context.activation()
                if self.context.current is None:follow_reasons.append(self.context.failure or 'fresh sensor context required')
            except (ValueError,OSError,KeyError) as exc:follow_reasons.append(str(exc))
        return dict(pet_observe=dict(available=True,qualified=False,reasons=['species/identity remain hypotheses']),
                    pet_follow=dict(available=not follow_reasons,qualified=not follow_reasons,reasons=follow_reasons))

    def accept_attention(self,result,decision):
        self.yield_reason=None
        self.intent=decision['intent'];self.last_decision=decision
        if self.intent!='follow':
            self.gate.close()
            execution=dict(dispatched=False,approved=False,rejected=['attention_'+self.intent],executed=None)
        else:
            try:
                from experiments.ppal.mobile_navigation import QualifiedMobileExecutor, MotionLease
                active,report=self.context.activation()
                if result['proposal'].get('reasons') or result['proposal'].get('action')=='stop':
                    raise ValueError('planner safety veto; no actuator connection')
                if self.executor is None:
                    # No transport is even constructed until independent admission.
                    self.base=self.base_factory();self.base.connect()
                    self.executor=QualifiedMobileExecutor(self.base,self.context,clock=self.perception.clock)
                    self.gate=MobileExecutionGate(backend=self.executor,clock=self.perception.clock,
                        boot_id=self.context.boot_id,safety_check=self.context.safe)
                expires=min(active['authorization']['expires_at'],self.perception.clock()+.4)
                self.gate.lease=MotionLease(active['authorization']['mode'],expires,active['activation_key'],self.context.boot_id)
                result['proposal']['binding']=QualifiedMobileExecutor.binding(self.context.current)
                execution=self.gate.execute(result['proposal'])
            except (ValueError,OSError,KeyError,TypeError,AttributeError) as exc:
                self.gate.close();execution=dict(dispatched=False,approved=False,rejected=['readiness_changed'],error=str(exc),executed=None)
        self.last_execution=execution;result['execution']=execution;result['attention']=decision
        key=(result['tracking']['target']['id'],decision['intent'],decision.get('project_id'),tuple(execution.get('rejected',[])))
        at=self.perception.clock()
        if key!=self.last_attention_key or execution.get('dispatched') or self.decision_at is None or at-self.decision_at>=2:
            self.evidence.attention_outcome(result,decision,execution,phase='bounded_attempt' if execution.get('dispatched') else 'considered')
            self.last_attention_key=key;self.decision_at=at

    def yield_attention(self,reason,result=None):
        self.gate.close();self.intent='yield'
        self.last_execution=dict(dispatched=False,approved=False,rejected=[reason],executed=None)
        self.last_decision=dict(intent='yield',reason=reason,project_id=(self.last_decision or {}).get('project_id'))
        previous=getattr(self,'yield_reason',None);self.yield_reason=reason
        self.last_attention_key=None
        if result:
            result['execution']=self.last_execution;result['attention']=self.last_decision
        if result and previous!=reason:self.evidence.attention_outcome(result,self.last_decision,self.last_execution,phase='yield/bookmark')

    def follow_step(self):
        # Catalog discovery/invocation cannot create a selected intent or repeat a start.
        if self.intent!='follow':raise ValueError('existing AttentionManager/Executive must select follow')
        return self.last_execution
