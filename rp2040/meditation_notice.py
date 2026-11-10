"""Display-only, sequence/session-bound MicroPython notice lease. No actuation."""
PHASES = ('PREPARING', 'MEDITATING', 'THINKING', 'CLEAR')


def request(session, slot, sequence, ttl_ms, phase):
    if (not isinstance(session, str) or not session or len(session)>40 or ' ' in session
            or not isinstance(slot,str) or len(slot)!=32 or any(c not in '0123456789abcdef' for c in slot)
            or type(sequence) is not int or not 1<=sequence<=2147483647 or phase not in PHASES
            or type(ttl_ms) is not int or (ttl_ms!=0 if phase=='CLEAR' else not 500<=ttl_ms<=10000)):
        raise ValueError('INVALID_MEDITATION_NOTICE')
    return 'MEDITATION %s %s %d %d %s' % (session,slot,sequence,ttl_ms,phase)


class Notice:
    def __init__(self, clock):
        self.clock=clock;self.session=None;self.sequence=0;self.slot=None
        self.closed=None;self.phase='CLEAR';self.until=0;self.packet=None

    def reset(self, session=None):
        self.session=session;self.sequence=0;self.slot=None;self.closed=None
        self.phase='CLEAR';self.until=0;self.packet=None

    def cancel(self):
        if self.slot:self.closed=self.slot
        self.slot=None;self.phase='CLEAR';self.until=0

    def status(self, visible=False):
        now=self.clock.ticks_ms()
        remaining=max(0,self.clock.ticks_diff(self.until,now)) if self.slot else 0
        if self.slot and not remaining:self.cancel()
        return dict(session=self.session,slot=self.slot,sequence=self.sequence,phase=self.phase,
                    remaining_ms=remaining,visible=bool(visible and self.slot))

    def apply(self, session, slot, sequence, ttl_ms, phase):
        packet=request(session,slot,sequence,ttl_ms,phase)
        self.status()
        if session!=self.session:raise ValueError('MEDITATION_SESSION')
        if sequence==self.sequence and packet==self.packet:return False
        if sequence<=self.sequence:raise ValueError('STALE_MEDITATION_NOTICE')
        if phase!='CLEAR' and (slot==self.closed or (self.slot and slot!=self.slot)):
            raise ValueError('CLOSED_OR_OCCUPIED_MEDITATION_NOTICE')
        if phase not in ('PREPARING','CLEAR') and self.slot!=slot:
            raise ValueError('MEDITATION_NOT_RESERVED')
        if phase=='CLEAR' and self.slot and self.slot!=slot:raise ValueError('MEDITATION_SLOT')
        self.sequence=sequence;self.packet=packet
        if phase=='CLEAR':self.closed=slot;self.cancel()
        else:
            self.slot=slot;self.phase=phase
            self.until=self.clock.ticks_add(self.clock.ticks_ms(),ttl_ms)
        return True
