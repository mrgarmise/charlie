"""Wire authorization for the existing arcade clients; never selects actions.

Vocabulary verified against charlie-arcade 3e6f708/src/controller.py. COIN is
the existing SELECT/BACK input alias, not a claim about its effect in a game.
Machine QUIT/operator-selection commands are outside a controller session.
"""
import re

BUTTONS = ('A', 'B', 'X', 'Y', 'LB', 'RB', 'BACK', 'START',
           'LS_CLICK', 'RS_CLICK', 'LT')
DEVICES = ('LS', 'RS', 'DPAD')
POSITIONS = ('CENTER', 'UP', 'UP_RIGHT', 'RIGHT', 'DOWN_RIGHT', 'DOWN',
             'DOWN_LEFT', 'LEFT', 'UP_LEFT')
ALIASES = {'COIN': 'BACK', 'SELECT': 'BACK', 'BTN_SELECT': 'BACK',
           'BTN_MODE': 'GUIDE', 'MODE': 'GUIDE', 'HOME': 'GUIDE',
           'BTN_HOME': 'GUIDE', 'GUIDE_BUTTON': 'GUIDE', 'HOME_BUTTON': 'GUIDE',
           'XBOX_GUIDE': 'GUIDE', 'XBOX_HOME': 'GUIDE', 'RIGHT_TRIGGER': 'RT',
           'R2': 'RT', 'ABS_RZ': 'RT', 'LEFT_TRIGGER': 'LT', 'L2': 'LT'}


def control_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_]+', value):
        raise ValueError('one controller token required')
    name = ALIASES.get(value.upper(), value.upper())
    if name == 'GUIDE':
        raise ValueError('Guide/Home prohibited unconditionally')
    if name == 'RT':
        raise ValueError('right trigger prohibited')
    if name not in BUTTONS and name not in {d+'_'+p for d in DEVICES for p in POSITIONS}:
        raise ValueError('unsupported controller token')
    return name


def validate_controls(controls, held=()):
    if isinstance(controls, str):
        raise ValueError('controls must be a sequence of tokens')
    names = tuple(control_name(c) for c in controls)
    # Held-state aliases are checked as strictly as newly requested controls.
    for value in held:
        control_name(value)
    return names


class ControllerSandbox:
    def __init__(self):
        self.held = set()

    def prepare(self, command):
        # No whitespace/newlines/compound strings: the server strips and
        # uppercases, so authorize the exact canonical bytes it will receive.
        if not isinstance(command, str) or not re.fullmatch(r'[A-Za-z0-9_]+', command):
            raise ValueError('one controller token required')
        command = command.upper()
        if command == 'NEUTRAL':
            return command, set()
        validate_controls((), self.held)
        # Absolute positions take precedence over legacy UP/DOWN suffixes.
        if command in {d+'_'+p for d in DEVICES for p in POSITIONS}:
            return command, set(self.held)
        suffix = next((s for s in ('_DOWN', '_UP') if command.endswith(s)), '')
        name = control_name(command[:-len(suffix)] if suffix else command)
        held = set(self.held)
        if suffix == '_UP':
            held.discard(name)
        else:
            validate_controls((name,), held)
            if suffix == '_DOWN':
                held.add(name)
        return name+suffix, held

    def commit(self, held):
        try:
            self.held = set(validate_controls(held))
        except ValueError:
            self.held.clear()
            raise


def validate_bridge_message(message):
    """The JSON bridge has only its original move/fire vocabulary, no aliases."""
    if not isinstance(message, dict) or message.get('type') not in ('step', 'release'):
        raise ValueError('unsupported bridge command')
    keys = {'type', 'sequence', 'buttons'} | ({'duration_ms'} if message['type']=='step' else set())
    if set(message) != keys:raise ValueError('unsupported bridge fields')
    if not isinstance(message.get('sequence'), int) or message['sequence'] < 1:
        raise ValueError('invalid command sequence')
    buttons = message.get('buttons')
    allowed = {prefix+d for prefix in ('move_', 'fire_') for d in ('up', 'down', 'left', 'right')}
    if not isinstance(buttons, list) or any(b not in allowed for b in buttons):
        raise ValueError('unsupported bridge controls')
    if message['type'] == 'release':
        if buttons: raise ValueError('release cannot press controls')
    elif not isinstance(message.get('duration_ms'), int) or not 30 <= message['duration_ms'] <= 500:
        raise ValueError('duration_ms must be 30..500')
