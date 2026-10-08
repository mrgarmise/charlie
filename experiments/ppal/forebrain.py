"""Persistent objective selection. No joystick commands live here."""

from .models import Action, Goal, WorldState


class Forebrain:
    def __init__(self, policy=None) -> None:
        self.goal: Goal | None = None
        self.policy = policy
        self.last_reason = {}
        self.exploration_trials = {}
        self.exploration_history = []

    def exploratory_action(self, screen, controls=None):
        """Choose novel controller hypotheses, not a taught startup sequence.

        Input labels describe hardware, never successful game effects. Counts
        are session-local diagnostic experience, not a deployed learned policy.
        """
        from .controller_sandbox import BUTTONS, validate_controls
        names=tuple(controls) if controls is not None else BUTTONS
        options=[Action(controls=(name,),reason='test unestablished controller effect') for name in names]
        if controls is None:
            options += [Action(move,fire,'test unestablished stick effect') for move,fire in
                        (('N','NONE'),('E','NONE'),('S','NONE'),('W','NONE'),('STAY','N'),('STAY','E'),('STAY','S'),('STAY','W'))]
        for action in options:validate_controls(action.controls)
        def key(action):return (action.move,action.fire,action.controls)
        # A changed scene provides a new context in which a previously tried
        # action may respond differently. Global coverage breaks ties; no
        # conditional COIN -> START rule or successful sequence is installed.
        context=screen.get('context','unknown')
        selected=min(options,key=lambda a:(self.exploration_trials.get((context,key(a)),0),
                    sum(n for (c,k),n in self.exploration_trials.items() if k==key(a)),options.index(a)))
        k=(context,key(selected));self.exploration_trials[k]=self.exploration_trials.get(k,0)+1
        if len(self.exploration_trials)>128:
            self.exploration_trials.pop(next(iter(self.exploration_trials)))
        self.last_reason=dict(reason=selected.reason,question='Does this permitted input change the observed environment?',
            context=context,interpretation='exploration authorization is not gameplay verification')
        return selected

    def exploratory_outcome(self, outcome):
        self.exploration_history.append(outcome)
        self.exploration_history=self.exploration_history[-32:]

    def update(self, world: WorldState) -> Goal:
        values = self.policy.values('goal_preference') if self.policy and world.observation_safe else {}
        self.last_reason = dict(reason='existing nearest persistent rescue objective',
            policy=self.policy.trace(['goal_preference'] if values else [],
                disposition='eligible' if world.observation_safe else 'unsafe observation') if self.policy else None)
        if not world.alive:
            self.goal = Goal("survive")
            return self.goal
        if not world.observation_safe:
            self.goal = Goal('survive')
            self.last_reason['reason'] = 'unsafe observation; conservative goal'
            return self.goal
        if values and values.get('survive', 0) > values.get('rescue', 1):
            self.goal = Goal('survive')
            self.last_reason['reason'] = 'qualified goal preference'
            return self.goal
        ids = {target.id for target in world.targets}
        if self.goal and self.goal.kind == "rescue" and self.goal.target_id in ids:
            return self.goal
        if world.targets:
            weight = values.get('target_threat_weight', 0)
            def cost(item):
                clearance = min((item.position.distance(t.position) for t in world.threats), default=100)
                return world.player.distance(item.position) + weight * (100-clearance)
            target = min(world.targets, key=cost)
            self.goal = Goal("rescue", target.id)
        else:
            self.goal = Goal("survive")
        return self.goal
