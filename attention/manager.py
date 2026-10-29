class AttentionManager:

    def __init__(self, bus, *, mobile_enabled=True, object_labels=None, emergency_stop=None):
        self.bus = bus
        self.deck = None
        self.object_labels = object_labels
        self.object_attention = None
        self.visual_target = None
        self.active = None
        self.priority = 0
        self.pending = None
        self.pet_service = None
        self.emergency_stopped = False
        self.emergency_stop_callback = emergency_stop
        self.face_service = None
        self.demonstration = None

        # Independent Elegoo mobile-attention sidecar.
        # This does not replace or modify the RP2040 TrackBehavior.
        self.mobile = None
        self.mobile_enabled = mobile_enabled

    def _ensure_mobile(self):
        if self.pet_service is not None or not self.mobile_enabled:
            return None
        if self.mobile is None:
            from behaviors.mobile_track import MobileTrackBehavior

            self.mobile = MobileTrackBehavior()
            self.mobile.enter()

        return self.mobile

    def set(self, behavior, deck, priority=0):
        """Request a behavior change (safe, queued)."""
        self.pending = (behavior, priority)

    def attach_pet_service(self, service, executive, registry):
        if self.mobile is not None:raise ValueError('legacy mobile controller owns ELEGOO; yield before pet service')
        self.pet_service=service;self.pet_executive=executive;self.pet_registry=registry

    def _consider_pet(self, result):
        service=self.pet_service
        if service is None:return
        opportunity=result['tracking'].get('target')
        if opportunity is None:
            service.yield_attention('target_lost_or_ambiguous',result)
            return
        if self.emergency_stopped:
            service.yield_attention('emergency_stop_latched',result)
            return
        readiness=service.readiness()
        resources={'mobile-camera','mobile-models'} if readiness['pet_observe']['available'] else set()
        if readiness['pet_follow']['available']:resources|={'qualified-car-local-controller','motion-lease'}
        # Existing registry + whole Executive portfolio, not a pet-only ranker.
        methods={p['method'] for p in self.pet_executive.projects().values()}
        available={c['id'] for c in self.pet_registry.describe()}
        methods &= available
        from learning.cycle import gameplay_active
        if gameplay_active():
            service.yield_attention('primary_gameplay_resource_ownership',result);return
        key=(opportunity['id'],max(self.priority,self.pending[1] if self.pending else 0),
             readiness['pet_follow']['available'])
        at=service.perception.clock()
        if (getattr(self,'pet_choice_key',None)==key and at-getattr(self,'pet_choice_at',0)<2
                and getattr(self,'pet_choice',None) is not None):
            service.accept_attention(result,self.pet_choice);return
        decision=self.pet_executive.consider_mobile_attention(result['evidence_id'],
            primary_priority=max(self.priority,self.pending[1] if self.pending else 0),
            methods=methods,resources=resources|service.executive_resources,
            authorized_methods=methods-({'pet_follow'} if not readiness['pet_follow']['available'] else set()))
        self.pet_choice_key=key;self.pet_choice_at=at;self.pet_choice=decision
        service.accept_attention(result,decision)

    def demonstration_unavailable(self):
        if self.emergency_stopped:return 'emergency_stop_latched'
        if self.pending or self.priority > 0:return 'current_attention_cannot_be_interrupted'
        if self.mobile is not None or self.face_service is not None or self.pet_service is not None:
            return 'active_body_service_cannot_be_interrupted'
        if self.active is not None:
            from behaviors.idle import IdleBehavior
            if not isinstance(self.active, IdleBehavior):return 'activity_has_no_safe_resume_contract'
        return None

    def handle_event(self, event, data):
        if event == 'operator_demonstration':
            if self.demonstration is not None:self.demonstration.begin(data)
            return
        if self.demonstration is not None and self.demonstration.running and event in (
                'emergency_stop','scan','track','vision_target','calibrate_neck','confirm_neck_start',
                'elegoo_face_observation','mobile_opportunity','idle'):
            self.demonstration.finish('cancelled', 'preempted:'+event)

        if event == 'vision_source_frame':
            mobile=self._ensure_mobile() if data.source == 'elegoo-v4' else None
            if mobile is not None:mobile.mobile.bind_frame(data)
            return
        if event == 'elegoo_face_observation':
            service = data['service']
            self.face_service = service
            if self.emergency_stopped or self.priority > 1 or (self.pet_service is not None and self.pet_service.intent == 'follow'):
                service.yield_attention()
            else:
                service.attend(data)
            return
        if event in ('object_attention','object_observation','object_observation_fault'):
            try:self._handle_object_event(event,data)
            except Exception as exc:self.object_display_error=type(exc).__name__+': '+str(exc)[:128]
            return
        if event == 'mobile_opportunity':
            self._consider_pet(data)
            return
        if event == 'emergency_stop':
            self.emergency_stopped = True
            if self.emergency_stop_callback is not None:
                try:self.emergency_stop_callback()
                except Exception:pass
            if self.deck is not None:
                try:self.deck.stop()
                except Exception:pass
            if self.face_service is not None:self.face_service.yield_attention()
            if self.pet_service is not None:self.pet_service.yield_attention('emergency_stop')
            return
        if self.pet_service is not None and event in ('scan','vision_target','calibrate_neck','confirm_neck_start','pet_yield'):
            self.pet_choice_key=None
            self.pet_service.yield_attention(event)
        if event == 'pet_yield':return
        if event in ('calibrate_neck', 'confirm_neck_start'):
            self.deck.brain_calibration(confirm=event == 'confirm_neck_start')

        elif event == "scan":
            from behaviors.scan import ScanBehavior
            self.set(ScanBehavior(), None, priority=50)

        elif event == "vision_target":
            self.visual_target=data
            from behaviors.track import TrackBehavior

            # Existing RP2040 tracking path.
            if isinstance(self.active, TrackBehavior):
                self.active.set_target(*data)

            else:
                behavior = TrackBehavior()
                behavior.set_target(*data)
                self.set(behavior, None, priority=80)

            # Independent Elegoo mobile path.
            try:
                mobile = self._ensure_mobile()
                if mobile is not None:
                    mobile.set_target(*data)
            except Exception as exc:
                print(
                    f"MOBILE sidecar target error: {exc}",
                    flush=True
                )

        elif event == "vision_lost":
            self.visual_target=None
            from behaviors.track import TrackBehavior

            # Existing RP2040 path.
            if isinstance(self.active, TrackBehavior):
                self.active.target_lost()

            # Independent Elegoo path.
            if self.mobile is not None:
                try:
                    self.mobile.target_lost()
                except Exception as exc:
                    print(
                        f"MOBILE sidecar lost error: {exc}",
                        flush=True
                    )

        elif event == "idle":
            from behaviors.idle import IdleBehavior
            self.set(IdleBehavior(), None, priority=0)

        elif event == "track":
            from behaviors.track import TrackBehavior

            behavior = TrackBehavior()

            if data:
                behavior.set_target(*data)

                try:
                    mobile = self._ensure_mobile()
                    if mobile is not None:
                        mobile.set_target(*data)
                except Exception as exc:
                    print(
                        f"MOBILE sidecar track error: {exc}",
                        flush=True
                    )

            self.set(behavior, None, priority=80)

    def _handle_object_event(self,event,data):
        if event == 'object_attention':
            if data is None or (isinstance(data,dict) and isinstance(data.get('source'),str) and data.get('id') is not None):self.object_attention=data
        elif event == 'object_observation':
            if self.object_labels is not None:
                selected=self.object_attention or data.get('attention_target')
                # Existing Pi attention coordinates are in the primary 1280x720
                # frame. Never apply these to ELEGOO or another camera source.
                if selected is None and data.get('source')=='pi-primary' and self.visual_target is not None:
                    geometry=data.get('geometry',())
                    if len(geometry)==2 and all(type(v) in (int,float) and v>0 for v in geometry):
                        x=self.visual_target[0]*geometry[0]/1280
                        y=self.visual_target[1]*geometry[1]/720
                        boxes=[r for r in data.get('objects',[]) if len(r.get('box',()))==4 and r['box'][0]<=x<=r['box'][2] and r['box'][1]<=y<=r['box'][3]]
                        if boxes:
                            chosen=max(boxes,key=lambda r:(r.get('confidence',0),str(r.get('id'))))
                            selected=dict(source=data['source'],id=chosen.get('id'))
                self.object_labels.observe(data,selected)
        elif event == 'object_observation_fault':
            if self.object_labels is not None:self.object_labels.invalidate(data)

    def update(self, deck):
        self.deck = deck

        # STOP preempts other already queued intents in this update. It is a
        # session latch; a later attention or registry event cannot clear it.
        events = self.bus.get_all()
        for event, data in events:
            if event == 'emergency_stop':self.handle_event(event, data)
        for event, data in events:
            if event != 'emergency_stop':self.handle_event(event, data)

        if self.object_labels is not None:
            try:self.object_labels.tick()
            except Exception as exc:self.object_display_error=type(exc).__name__+': '+str(exc)[:128]

        # Preserve the existing behavior instance/bookmark; no enter/exit, chooser
        # or movement update while the stationary operator ability has attention.
        if self.demonstration is not None and self.demonstration.running:return

        # Apply pending RP2040 behavior switch second.
        if self.pending:
            behavior, priority = self.pending
            self.pending = None
            self._switch(
                behavior,
                deck,
                priority
            )

        # Run existing RP2040 behavior.
        if self.active:
            self.active.update(deck)

            if (
                hasattr(
                    self.active,
                    "is_finished"
                )
                and self.active.is_finished()
            ):
                from behaviors.idle import IdleBehavior

                self.set(
                    IdleBehavior(),
                    deck,
                    priority=0
                )

        # Run independent Elegoo behavior.
        if self.mobile is not None:
            try:
                self.mobile.update()
            except Exception as exc:
                print(
                    f"MOBILE sidecar update error: {exc}",
                    flush=True
                )

                try:
                    self.mobile.target_lost()
                except Exception:
                    pass

    def _switch(
        self,
        behavior,
        deck,
        priority
    ):

        if self.active:
            self.active.exit(deck)

        self.active = behavior
        self.priority = priority
        self.active.enter(deck)
        self.attach(self.active)

    def attach(self, behavior):
        behavior.attention = self

    def set_scan(self):
        from behaviors.scan import ScanBehavior
        self.set(
            ScanBehavior(),
            None,
            priority=50
        )

    def close(self):
        """
        Stop the mobile sidecar cleanly when Charlie shuts down.
        """
        if self.object_labels is not None:
            try:self.object_labels.close()
            except Exception as exc:self.object_display_error=type(exc).__name__+': '+str(exc)[:128]
        if self.pet_service is not None:
            self.pet_service.yield_attention('application_shutdown')
        if self.mobile is not None:
            try:
                self.mobile.exit()
            except Exception:
                pass

            self.mobile = None
