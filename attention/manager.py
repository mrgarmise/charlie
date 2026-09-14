class AttentionManager:

    def __init__(self, bus):
        self.bus = bus
        self.active = None
        self.priority = 0
        self.pending = None

        # Independent Elegoo mobile-attention sidecar.
        # This does not replace or modify the RP2040 TrackBehavior.
        self.mobile = None

    def _ensure_mobile(self):
        if self.mobile is None:
            from behaviors.mobile_track import MobileTrackBehavior

            self.mobile = MobileTrackBehavior()
            self.mobile.enter()

        return self.mobile

    def set(self, behavior, deck, priority=0):
        """Request a behavior change (safe, queued)."""
        self.pending = (behavior, priority)

    def handle_event(self, event, data):
        if event == "scan":
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
                self._ensure_mobile().set_target(*data)
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
                    self._ensure_mobile().set_target(*data)
                except Exception as exc:
                    print(
                        f"MOBILE sidecar track error: {exc}",
                        flush=True
                    )

            self.set(behavior, None, priority=80)

    def update(self, deck):

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
        if self.mobile is not None:
            try:
                self.mobile.exit()
            except Exception:
                pass

            self.mobile = None
