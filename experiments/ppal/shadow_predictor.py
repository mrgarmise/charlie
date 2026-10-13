"""Live Robotron shadow prediction.

Predicts the next short-horizon WorldState from persistent gameplay-object IDs.
The shadow brain may recommend an action, but it never touches the controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite

from .models import Object, Position, WorldState


@dataclass
class _Motion:
    tick: int
    position: Position
    vx: float = 0.0
    vy: float = 0.0
    observations: int = 1


class ShadowPredictor:
    """Causal constant-velocity projector for live PPAL shadow evaluation."""

    def __init__(self, horizon_ticks: int = 1, velocity_alpha: float = 0.65,
                 max_speed: float = 12.0, horizon_seconds: float | None = None) -> None:
        if horizon_seconds is not None and (not isfinite(horizon_seconds) or horizon_seconds <= 0):
            raise ValueError('horizon_seconds must be positive and finite')
        self.horizon_seconds = horizon_seconds
        self.observed_at = None
        self.horizon_ticks = int(horizon_ticks)
        self.velocity_alpha = float(velocity_alpha)
        self.max_speed = float(max_speed)
        self._objects: dict[str, _Motion] = {}
        self._player: _Motion | None = None

    def _update_motion(self, previous: _Motion | None, tick: int,
                       position: Position) -> _Motion:
        if previous is None or tick <= previous.tick:
            return _Motion(tick, position)
        dt = tick - previous.tick
        raw_vx = (position.x - previous.position.x) / dt
        raw_vy = (position.y - previous.position.y) / dt
        speed = hypot(raw_vx, raw_vy)
        if speed > self.max_speed:
            scale = self.max_speed / speed
            raw_vx *= scale
            raw_vy *= scale
        if previous.observations < 2:
            vx, vy = raw_vx, raw_vy
        else:
            a = self.velocity_alpha
            vx = a * raw_vx + (1.0 - a) * previous.vx
            vy = a * raw_vy + (1.0 - a) * previous.vy
        return _Motion(tick, position, vx, vy, previous.observations + 1)

    def observe(self, world: WorldState, timestamp: float | None = None) -> None:
        if self.horizon_seconds is not None:
            if timestamp is None or not isfinite(timestamp):
                raise ValueError('time-based prediction requires a finite capture timestamp')
            if self.observed_at is not None and timestamp <= self.observed_at:
                raise ValueError('capture timestamps must increase')
            self.observed_at = timestamp
        moment = timestamp if self.horizon_seconds is not None else world.tick
        self._player = self._update_motion(self._player, moment, world.player)
        seen = set()
        for item in (*world.targets, *world.threats, *world.unresolved):
            seen.add(item.id)
            self._objects[item.id] = self._update_motion(
                self._objects.get(item.id), moment, item.position)
        # ObjectTracker already handles brief visual absence. Do not preserve
        # stale shadow velocity after a semantic object disappears.
        self._objects = {k: v for k, v in self._objects.items() if k in seen}

    @staticmethod
    def _project(motion: _Motion, horizon: int) -> Position:
        return Position(
            max(0.0, min(100.0, motion.position.x + motion.vx * horizon)),
            max(0.0, min(100.0, motion.position.y + motion.vy * horizon)),
        )

    def project(self, world: WorldState) -> WorldState:
        """Return anticipated state; caller must have called observe(world)."""
        horizon = self.horizon_seconds if self.horizon_seconds is not None else self.horizon_ticks
        player = (self._project(self._player, horizon)
                  if self._player is not None else world.player)

        def projected(items):
            result = []
            for item in items:
                motion = self._objects.get(item.id)
                pos = self._project(motion, horizon) if motion else item.position
                result.append(Object(item.id, pos))
            return tuple(result)

        return WorldState(
            tick=world.tick + self.horizon_ticks,
            player=player,
            targets=projected(world.targets),
            threats=projected(world.threats),
            alive=world.alive,
            unresolved=projected(world.unresolved),
        )

    def snapshot(self, world: WorldState, projected: WorldState) -> dict:
        def rows(now, future):
            by_id = {x.id: x for x in future}
            out = []
            for item in now:
                later = by_id[item.id]
                motion = self._objects.get(item.id)
                out.append({
                    "id": item.id,
                    "now": [round(item.position.x, 3), round(item.position.y, 3)],
                    "predicted": [round(later.position.x, 3),
                                  round(later.position.y, 3)],
                    "velocity": ([round(motion.vx, 3), round(motion.vy, 3)]
                                 if motion else [0.0, 0.0]),
                })
            return out

        pm = self._player
        return {
            "horizon_ticks": self.horizon_ticks,
            "horizon_seconds": self.horizon_seconds,
            "observed_at": self.observed_at,
            "velocity_units": "board_percent_per_second" if self.horizon_seconds is not None else "board_percent_per_tick",
            "prediction_kind": "constant_velocity_diagnostic_not_action_counterfactual",
            "player_now": [round(world.player.x, 3), round(world.player.y, 3)],
            "player_predicted": [round(projected.player.x, 3),
                                 round(projected.player.y, 3)],
            "player_velocity": ([round(pm.vx, 3), round(pm.vy, 3)]
                                if pm else [0.0, 0.0]),
            "targets": rows(world.targets, projected.targets),
            "threats": rows(world.threats, projected.threats),
            "unresolved": rows(world.unresolved, projected.unresolved),
        }


def action_dict(action) -> dict:
    fire = "NONE" if action.fire == "STAY" else action.fire
    result={"move": action.move, "fire": fire, "reason": action.reason}
    if action.controls:result['controls']=list(action.controls)
    return result
