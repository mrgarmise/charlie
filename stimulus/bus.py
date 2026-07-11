class StimulusBus:
    def __init__(self):
        self.events = []
        
    def emit(self, event_type, data=None):
        self.events.append((event_type, data))
        
    def get_all(self):
        events = self.events[:]
        self.events = []
        return events
    