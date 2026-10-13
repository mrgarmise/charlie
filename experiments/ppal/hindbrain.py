"""Short-horizon tactics plus an immediate collision override."""

from math import hypot
from typing import TYPE_CHECKING

from .models import Action, Goal, Intent, Position, WorldState

if TYPE_CHECKING:
    from .shot_learning import ShotModel


MOVE_VECTORS = {"N": (0, -1), "NE": (1, -1), "E": (1, 0), "SE": (1, 1),
                "S": (0, 1), "SW": (-1, 1), "W": (-1, 0), "NW": (-1, -1)}


def direction(start: Position, end: Position, deadband: float = 3) -> str:
    dx, dy = end.x - start.x, end.y - start.y
    horizontal = "E" if dx > deadband else "W" if dx < -deadband else ""
    vertical = "S" if dy > deadband else "N" if dy < -deadband else ""
    return vertical + horizontal or "STAY"


def distance_to_segment(point: Position, start: Position, end: Position) -> float:
    dx, dy = end.x - start.x, end.y - start.y
    denominator = dx * dx + dy * dy
    if denominator == 0:
        return point.distance(start)
    fraction = max(0.0, min(1.0, ((point.x - start.x) * dx + (point.y - start.y) * dy) / denominator))
    return point.distance(Position(start.x + fraction * dx, start.y + fraction * dy))


class Hindbrain:
    def __init__(self, panic_radius: float = 9, route_width: float = 9,
                 shot_model: "ShotModel | None" = None, explore_fire: bool = False, policy=None,
                 tactical_learning: bool = False) -> None:
        self.explore_fire = explore_fire
        self.fire_explorations = 0
        self.panic_radius = panic_radius
        self.route_width = route_width
        self.shot_model = shot_model
        self.policy = policy
        self.last_decision = {}
        self._applied = []
        self.last_clear_id: str | None = None
        self.last_clear_tick: int | None = None
        self.last_panic_hold_id: str | None = None
        self.last_panic_hold_tick: int | None = None
        self.last_open_move: str | None = None
        self.tactical_learning=tactical_learning
        self.tactical_plan={}
        self.tactical_outcome=None
        self._tactical_pending=None
        self._tactical_stats={}
        self._last_tactical_action=None
        self._tactical_number=0

    @staticmethod
    def _action_key(action):return action.move,action.fire

    def _tactical_options(self,world,goal,baseline):
        """Bounded alternatives derived from current observed geometry."""
        options=[baseline]
        if self._last_tactical_action is not None:options.append(self._last_tactical_action)
        for move in MOVE_VECTORS:
            options.append(Action(move,baseline.fire,'test alternative observed-safe movement'))
        if world.threats:
            fire=direction(world.player,min(world.threats,key=lambda t:world.player.distance(t.position)).position,0)
            options.append(Action(baseline.move,fire,'test current visual firing opportunity'))
            options.extend(Action(move,fire,'test movement and visual firing combination') for move in MOVE_VECTORS)
        unique={};occupants=(*world.threats,*world.unresolved)
        for action in options:
            if action.move in MOVE_VECTORS:
                dx,dy=MOVE_VECTORS[action.move];n=hypot(dx,dy)
                end=Position(world.player.x+8*dx/n,world.player.y+8*dy/n)
                if not (4<=end.x<=96 and 4<=end.y<=96):continue
                if any(distance_to_segment(o.position,world.player,end)<=4 for o in occupants):continue
            unique.setdefault(self._action_key(action),action)
        return list(unique.values())

    def _choose_tactic(self,world,goal,intent,baseline):
        self.tactical_plan={}
        if not self.tactical_learning:return intent,baseline
        mandatory=(not world.alive or not world.observation_safe or intent.kind=='evade'
            or any(world.player.distance(t.position)<self.panic_radius for t in world.threats))
        options=[baseline] if mandatory else self._tactical_options(world,goal,baseline)
        samples=self._tactical_stats.get(self._action_key(baseline),[])
        # Revise only after a completed eligible window contradicts the signed
        # motion hypothesis. Ambiguous/missing observations never penalize it.
        contradicted=bool(samples and samples[-1]['result']=='contradicted')
        selected=baseline
        if not mandatory and contradicted and options:
            target=next((o for o in world.targets if o.id==goal.target_id),None)
            def rank(a):
                history=self._tactical_stats.get(self._action_key(a),[])
                rejected=sum(s['result']=='contradicted' for s in history)
                dx,dy=MOVE_VECTORS.get(a.move,(0,0));n=hypot(dx,dy) or 1
                end=Position(world.player.x+8*dx/n,world.player.y+8*dy/n)
                return rejected,len(history),end.distance(target.position) if target else 0,options.index(a)
            selected=min(options,key=rank)
            if self._action_key(selected)!=self._action_key(baseline):
                selected=Action(selected.move,selected.fire,'revise contradictory tactical motion hypothesis')
                intent=Intent('investigate',destination=intent.destination,target_id=intent.target_id)
        self._tactical_number+=1
        self.tactical_plan=dict(id=f'tactical-{self._tactical_number}',
            question='Will the selected permitted movement produce a consistent signed response?',
            hypothesis=dict(move=selected.move,fire=selected.fire,expected='signed movement in the chosen direction' if selected.move in MOVE_VECTORS else 'neutral movement; firing effect unresolved',
                samples=len(self._tactical_stats.get(self._action_key(selected),[]))),
            options=[dict(move=a.move,fire=a.fire,reason=a.reason) for a in options],
            selected=dict(move=selected.move,fire=selected.fire),
            disposition='mandatory current-observation override' if mandatory else
                'revise after qualified contradiction' if contradicted else 'test or repeat current option',
            uncertainty='session-local diagnostic hypothesis; no verified score effect or persistent policy deployment')
        return intent,selected

    def align_tactical_action(self,action):
        """Record the actual final selection after existing guards/experiments."""
        if not self.tactical_plan:return
        actual=dict(move=action.move,fire=action.fire)
        if self.tactical_plan['selected']!=actual:
            self.tactical_plan['previous_selection']=self.tactical_plan['selected']
            self.tactical_plan['disposition']='existing guarded chooser or commissioned experiment override'
        self.tactical_plan['selected']=actual
        self.tactical_plan['hypothesis'].update(actual,
            expected='signed movement in the chosen direction' if action.move in MOVE_VECTORS else
                'neutral movement; firing effect unresolved')

    def executed_tactic(self,world,action,*,timestamp,track_id,prediction_id):
        if not self.tactical_learning:return
        self._tactical_pending=dict(world=world,action=action,timestamp=timestamp,track_id=track_id,
            prediction_id=prediction_id,plan=self.tactical_plan)
        self._last_tactical_action=action

    def interrupt_tactic(self,reason):
        p=self._tactical_pending
        self._tactical_pending=None;self._tactical_stats={};self._last_tactical_action=None
        if p is None:return None
        return dict(prediction_id=p['prediction_id'],result='unresolved',resolved_result='unresolved',eligible=False,
                    reason=reason,interpretation='interrupted observation is not failed action')

    def tactical_feedback(self,world,*,timestamp,track_id,identity_status,response_window=None):
        """Compare only actual, fresh, same-identity completed response windows."""
        self.tactical_outcome=None
        p=self._tactical_pending
        if p is None:return None
        self._tactical_pending=None
        if track_id!=p['track_id']:
            self._tactical_stats={};self._last_tactical_action=None
        window=response_window or {};action=p['action'];dt=timestamp-p['timestamp']
        eligible=(world.observation_safe and identity_status=='confirmed' and track_id is not None
            and track_id==p['track_id'] and 0<dt<=2 and window.get('endpoint')==2
            and window.get('origin_at')==p['timestamp'] and window.get('move')==action.move)
        dx=world.player.x-p['world'].player.x;dy=world.player.y-p['world'].player.y
        vx,vy=MOVE_VECTORS.get(action.move,(0,0));length=hypot(vx,vy) or 1
        along=(dx*vx+dy*vy)/length
        result='supported' if eligible and action.move in MOVE_VECTORS and along>=.2 else \
               'contradicted' if eligible and action.move in MOVE_VECTORS else 'unresolved'
        outcome=dict(prediction_id=p['prediction_id'],tactical_id=p['plan'].get('id'),
            origin_at=p['timestamp'],observed_at=timestamp,track_id=track_id,identity_status=identity_status,
            eligible=eligible,result=result,displacement=[dx,dy] if eligible else None,
            along=along if eligible else None,scene_changed=eligible and result=='supported',
            resolved_result=result,reason='same qualified track and completed causal response window' if eligible else
                'missing, late, ambiguous identity or incomplete response; no negative evidence',
            interpretation='short-horizon diagnostic; not an independently qualified strategy or score improvement')
        if eligible and action.move in MOVE_VECTORS:
            key=self._action_key(action);rows=self._tactical_stats.setdefault(key,[])
            rows.append(dict(result=result,along=along,prediction_id=p['prediction_id']))
            self._tactical_stats[key]=rows[-8:]
            if len(self._tactical_stats)>32:self._tactical_stats.pop(next(iter(self._tactical_stats)))
        self.tactical_outcome=outcome
        return outcome

    def _open_space(self, world: WorldState) -> tuple[Intent, Action]:
        # Unresolved objects are occupied space, not fabricated enemies or
        # rescues. Choose a bounded direction with the clearest route/endpoint.
        occupants = (*world.threats, *world.unresolved)
        candidates = []
        for move, (dx, dy) in MOVE_VECTORS.items():
            length = hypot(dx, dy)
            end = Position(world.player.x+8*dx/length, world.player.y+8*dy/length)
            if not (4 <= end.x <= 96 and 4 <= end.y <= 96):
                continue
            route = min((distance_to_segment(o.position, world.player, end)
                         for o in occupants), default=100.)
            clearance = min((end.distance(o.position) for o in occupants), default=100.)
            margin = min(end.x, end.y, 100-end.x, 100-end.y)
            bias = self.policy.values('positioning_preference') if self.policy else {}
            if bias and 'positioning_preference' not in self._applied:
                self._applied.append('positioning_preference')
            # Learned preference only arbitrates equally clear choices.
            candidates.append(((route, clearance, bias.get(move, 0), move == self.last_open_move, margin), move, end))
        if not candidates:
            return Intent("hold"), Action(reason="no bounded open-space step")
        _, move, end = max(candidates, key=lambda row:row[0])
        self.last_open_move = move
        threat = min(world.threats, key=lambda o:world.player.distance(o.position), default=None)
        fire = direction(world.player, threat.position, 0) if threat else 'NONE'
        if threat is None and self.explore_fire:
            fire = ('N','E','S','W')[self.fire_explorations % 4]
            self.fire_explorations += 1
        return (Intent("explore", destination=end),
                Action(move, fire, "seek open space; explore FIRE effects" if threat is None and self.explore_fire
                       else "seek open space; no current rescue target"))

    def decide(self, world: WorldState, goal: Goal, *, timestamp=None) -> tuple[Intent, Action]:
        self._applied = []
        intent, action = self._decide(world, goal, timestamp=timestamp)
        intent, action = self._choose_tactic(world,goal,intent,action)
        if self.policy and action.move in MOVE_VECTORS and world.unresolved:
            dx,dy=MOVE_VECTORS[action.move];length=hypot(dx,dy)
            end=Position(world.player.x+8*dx/length,world.player.y+8*dy/length)
            if any(end.distance(item.position)<=4 for item in world.unresolved):
                intent,action=Intent('hold'),Action('STAY',action.fire,'unresolved occupied next step; neutral movement')
        self.align_tactical_action(action)
        self.last_decision = dict(reason=action.reason, intent=intent.kind,
            policy=self.policy.trace(self._applied, disposition='immediate override' if intent.kind=='evade'
                or action.reason.startswith('clear close threat') else
                'unsafe observation' if not world.observation_safe else 'eligible') if self.policy else None)
        return intent, action

    def _decide(self, world: WorldState, goal: Goal, *, timestamp=None) -> tuple[Intent, Action]:
        if not world.alive:
            return Intent("hold"), Action(reason="world not alive")
        if not world.observation_safe:
            return Intent('hold'), Action(reason='unsafe observation; neutral')
        projected = self.policy.predicted_targets(world, timestamp) if self.policy else None
        nearby = [threat for threat in world.threats if world.player.distance(threat.position) < self.panic_radius]
        if nearby:
            threat = min(nearby, key=lambda item: world.player.distance(item.position))
            # At a short but non-contact distance, clear the threat without
            # abandoning the route. If that shot failed, dodge next tick.
            failed_hold = (self.last_panic_hold_id == threat.id
                           and self.last_panic_hold_tick is not None
                           and world.tick > self.last_panic_hold_tick)
            if world.player.distance(threat.position) > 6 and not failed_hold:
                self.last_panic_hold_id = threat.id
                self.last_panic_hold_tick = world.tick
                return (Intent("clear", threat.id, threat.position),
                        Action("STAY", direction(world.player, threat.position),
                               "clear close threat; preserve rescue route"))
            self.last_panic_hold_id = None
            self.last_panic_hold_tick = None
            escape = Position(2 * world.player.x - threat.position.x, 2 * world.player.y - threat.position.y)
            return (Intent("evade", threat.id, escape),
                    Action(direction(world.player, escape, 0), direction(world.player, threat.position, 0), "immediate threat"))

        self.last_panic_hold_id = None
        self.last_panic_hold_tick = None

        target = next((item for item in world.targets if item.id == goal.target_id), None)
        if target is None:
            return self._open_space(world)

        if projected is not None:
            target = next((item for item in projected if item.id == target.id), target)
            self._applied.append('action_effect_prediction')

        blockers = [threat for threat in world.threats
                    if distance_to_segment(threat.position, world.player, target.position) < self.route_width
                    and threat.position.distance(world.player) < target.position.distance(world.player)]
        if blockers:
            blocker = min(blockers, key=lambda item: world.player.distance(item.position))
            # Keep the rescue as the destination. If the same blocker survived
            # last tick's shot, advance while firing to improve the angle.
            repeated = (self.last_clear_id == blocker.id and self.last_clear_tick is not None
                        and world.tick > self.last_clear_tick)
            self.last_clear_id = blocker.id
            self.last_clear_tick = world.tick
            fire_values = self.policy.values('firing_behavior') if self.policy else {}
            fire = direction(world.player, blocker.position, fire_values.get('deadband', 3))
            if fire_values:self._applied.append('firing_behavior')
            predicted_miss = (self.shot_model is not None and not self.shot_model.likely_hit(
                world.player, blocker.position, fire))
            movement = direction(world.player, target.position) if repeated or predicted_miss else "STAY"
            if movement in MOVE_VECTORS:
                dx, dy = MOVE_VECTORS[movement]
                length = hypot(dx, dy)
                next_position = Position(max(0, min(100, world.player.x + 8 * dx / length)),
                                         max(0, min(100, world.player.y + 8 * dy / length)))
                if any(next_position.distance(item.position) <= 4 for item in world.threats):
                    movement = "STAY"
            return (Intent("clear", blocker.id, blocker.position),
                    Action(movement, fire,
                           "advance toward rescue after missed shot" if repeated else
                           "predicted miss; advance toward rescue" if movement != "STAY" else "clear route"))
        self.last_clear_id = None
        self.last_clear_tick = None
        movement = direction(world.player, target.position)
        if movement in MOVE_VECTORS:
            dx, dy = MOVE_VECTORS[movement]
            length = hypot(dx, dy)
            next_position = Position(max(0, min(100, world.player.x + 8 * dx / length)),
                                     max(0, min(100, world.player.y + 8 * dy / length)))
            collisions = [threat for threat in world.threats
                          if next_position.distance(threat.position) <= 4]
            if collisions:
                threat = min(collisions, key=lambda item: world.player.distance(item.position))
                return (Intent("clear", threat.id, threat.position),
                        Action("STAY", direction(world.player, threat.position),
                               "clear threat on next step toward rescue"))
        return (Intent("approach", target.id, target.position),
                Action(movement, "NONE", "approach target"))
