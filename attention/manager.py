class AttentionManager:

    def __init__(self, bus, *, mobile_enabled=True):
        self.bus = bus
        self.active = None
        self.priority = 0
        self.pending = None
        self.pet_service = None

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

    def handle_event(self, event, data):
        if event == 'mobile_opportunity':
            self._consider_pet(data)
            return
        if self.pet_service is not None and event in ('scan','vision_target','calibrate_neck','confirm_neck_start','emergency_stop','pet_yield'):
            self.pet_choice_key=None
            self.pet_service.yield_attention(event)
        if event in ('emergency_stop','pet_yield'):return
        if event in ('calibrate_neck', 'confirm_neck_start'):
            self.deck.brain_calibration(confirm=event == 'confirm_neck_start')

        elif event == "scan":
            from behaviors.scan import ScanBehavior
            self.set(ScanBehavior(), None, priority=50)

        elif event == "vision_target":
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

    def update(self, deck):
        self.deck = deck

        # Process stimuli first.
        for event, data in self.bus.get_all():
            self.handle_event(event, data)

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
        if self.pet_service is not None:
            self.pet_service.yield_attention('application_shutdown')
        if self.mobile is not None:
            try:
                self.mobile.exit()
            except Exception:
                pass

            self.mobile = None
