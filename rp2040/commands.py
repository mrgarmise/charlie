"""Strict RP2040 protocol. UART requests cannot grant physical permission."""
try:
    import ujson as json
except ImportError:
    import json
from servos import MotionError, number


def arguments(cmd, counts):
    values=getattr(cmd,'args',[])
    if len(values) not in counts:raise MotionError('MALFORMED_COMMAND')
    return values


def epoch(value):
    if not isinstance(value,str) or not value.isdigit():
        raise MotionError('INVALID_EPOCH')
    return int(value)


class CommandHandler:
    def __init__(self, behaviors, display, heartbeat):
        self.behaviors,self.display,self.heartbeat=behaviors,display,heartbeat

    def handle(self, cmd):
        if cmd is None:
            print('ERR MALFORMED_COMMAND')
            return
        servos=self.behaviors.servos
        try:
            servos.expire()
            name=cmd.name
            if name in ('LOOK','TRACK','HOME','SCAN','MOVE') and not servos.status()['armed']:
                raise MotionError('HEAD_MOTION_DISARMED')
            if name=='ARM':
                raise MotionError('LOCAL_PHYSICAL_ARM_REQUIRED')
            if name=='PING':
                arguments(cmd,(0,)); print('ALIVE')
            elif name=='SESSION':
                values=arguments(cmd,(1,));servos.establish_session(values[0])
                self.behaviors.set_mode(self.behaviors.IDLE)
                print('OK SESSION')
            elif name=='AUTHORIZE':
                owner,session,revision,transition=arguments(cmd,(4,))
                servos.authorize(owner,session,epoch(revision),transition)
                print('OK AUTHORIZE')
            elif name=='PRIMARY':
                session,revision=arguments(cmd,(2,))
                servos.primary_acquire(session,epoch(revision))
                self.behaviors.set_mode(self.behaviors.IDLE)
                print('OK PRIMARY')
            elif name=='MOTION_STATUS':
                arguments(cmd,(0,))
                print('MOTION_STATUS',json.dumps(servos.status()))
            elif name=='CAL_STATUS':
                arguments(cmd,(0,)); print('CAL_STATUS',json.dumps(servos.calibration.status()))
            elif name in ('CAL','START_VERIFY'):
                values=cmd.raw.split(None,3)
                if len(values)!=4: raise MotionError('MALFORMED_COMMAND')
                session,revision=values[1:3];data=json.loads(values[3])
                if not isinstance(data,dict): raise MotionError('INVALID_CAL_REQUEST')
                if name=='CAL':
                    servos.calibration.request(session,epoch(revision),data)
                    self.behaviors.set_mode(self.behaviors.IDLE)
                else: servos.confirm_start_pose(session,epoch(revision),data.get('pose'),data)
                print('OK',name)
            elif name=='AUTOSTART':
                session,revision=arguments(cmd,(2,))
                servos.activate_autonomous(session,epoch(revision));print('OK AUTOSTART')
            elif name=='NECK_UNCERTAIN':
                session,revision,reason=arguments(cmd,(3,))
                servos.validate_control(session,epoch(revision))
                servos.invalidate_profile(reason);print('OK NECK_UNCERTAIN')
            elif name=='VIEWPOINT':
                arguments(cmd,(0,));s=servos.status()
                print('VIEWPOINT',s['pan'],s['tilt'],90.0,90.0,int(s['moving']),
                      self.behaviors.mode,s['state'])
            elif name=='STATUS':
                arguments(cmd,(0,));print('MODE',self.behaviors.mode,servos.status()['state'])
            elif name in ('STOP','IDLE','SLEEP'):
                arguments(cmd,(0,))
                # IDLE and SLEEP must not leave a pending servo target alive.
                servos.stop(name)
                self.behaviors.set_mode(self.behaviors.SLEEP if name=='SLEEP' else self.behaviors.IDLE)
                print('OK',name)
            elif name=='MOVE':
                session,revision,pan,tilt,rate=arguments(cmd,(5,))
                self.behaviors.gaze(number(pan),number(tilt),number(rate),
                                    session=session,epoch=epoch(revision))
                print('OK MOVE')
            elif name in ('LOOK','TRACK'):
                # Familiar names retained, but no default angle or implicit
                # authorization. Unscoped legacy requests are rejected.
                values=arguments(cmd,(4,5))
                pan,tilt=number(values[0]),number(values[1])
                if len(values)==5:rate=number(values[2]);session,revision=values[3:]
                else:rate=None;session,revision=values[2:]
                method=self.behaviors.gaze if name=='LOOK' else self.behaviors.look
                method(pan,tilt,rate,session=session,epoch=epoch(revision))
                print('OK',name)
            elif name in ('HOME','SCAN'):
                session,revision=arguments(cmd,(2,))
                method=self.behaviors.home if name=='HOME' else self.behaviors.scan
                method(session=session,epoch=epoch(revision))
                print('OK',name)
            elif name in ('THINK','HAPPY','ERROR'):
                arguments(cmd,(0,))
                if self.display:self.display.feedback(getattr(self.display,name),1800)
                print('OK',name)
            elif name=='PROGRESS':
                values=arguments(cmd,(1,));value=number(values[0])
                if value != int(value) or not 0<=value<=100:
                    raise MotionError('INVALID_PROGRESS')
                if self.display:self.display.set_progress(int(value))
                print('OK PROGRESS')
            elif name=='PROGRESS_CLEAR':
                arguments(cmd,(0,))
                if self.display:self.display.clear_progress()
                print('OK PROGRESS_CLEAR')
            elif name=='MESSAGE':
                values=arguments(cmd,tuple(range(1,33)))
                if self.display:self.display.show_text(' '.join(values))
                print('OK MESSAGE')
            elif name in ('RX','TX'):
                arguments(cmd,(0,))
                if self.display:getattr(self.display,name.lower()+'_activity')()
                print('OK',name)
            else:
                raise MotionError('UNKNOWN_COMMAND')
            servos.contact()
            self.heartbeat.beat()
        except (MotionError, ValueError, TypeError) as exc:
            print('ERR',str(exc))
