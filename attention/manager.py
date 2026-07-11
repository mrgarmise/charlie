class AttentionManager:

    def __init__(self, bus):
        self.bus = bus
        self.active = None
        self.priority = 0
        self.pending = None

    def set(self, behavior, deck, priority=0):
        """Request a behavior change (safe, queued)."""
        self.pending = (behavior, priority)
        
    def handle_event(self, event, data):
        if event == "scan":
            from behaviors.scan import ScanBehavior
            self.set(ScanBehavior(), None, priority=50)
        elif event == "idle":
            from behaviors.idle import IdleBehavior
            self.set(IdleBehavior(), None, priority=0)
        elif event == 'track':
            from behaviors.track import TrackBehavior
            behavior = TrackBehavior()
            
            if data:
                behavior.set_target(*data)
                
            self.set(TrackBehavior(), data, priority = 80)
            
    def update(self, deck):

        #process stimuli first
        for event, data in self.bus.get_all():
                self.handle_event(event, data)

        # apply pending switch second
        if self.pending:
            behavior, priority = self.pending
            self.pending = None
            self._switch(behavior, deck, priority)

        # run active behavior
        if self.active:
            self.active.update(deck)

            # auto-finish handling
            if hasattr(self.active, "is_finished") and self.active.is_finished():
                from behaviors.idle import IdleBehavior
                self.set(IdleBehavior(), deck, priority=0)

    def _switch(self, behavior, deck, priority):

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
        self.set(ScanBehavior(), None, priority=50)
        
