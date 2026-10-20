"""Offline interpretation of reviewed reserve icons; no gameplay authority.

This is not a pixel detector. Counts must come from independent HUD review or
a separately qualified reader. Never pass these counts to HUDObservation.lives:
reserve icons exclude the active life. Unknown/occluded HUD is not zero.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ReserveObservation:
    episode: str
    channel: str
    observation_id: str
    source_sha256: str
    timestamp: float
    count: int | None
    hud_visible: bool
    reviewed: bool

    def __post_init__(self):
        if not all(isinstance(x, str) and x for x in
                   (self.episode, self.channel, self.observation_id)):
            raise ValueError("episode, channel and observation identity required")
        if (not isinstance(self.source_sha256, str) or len(self.source_sha256) != 64
                or any(c not in '0123456789abcdef' for c in self.source_sha256)):
            raise ValueError("original image SHA-256 required")
        if (type(self.timestamp) not in (float, int)
                or not math.isfinite(self.timestamp)):
            raise ValueError("finite exposure timestamp required")
        if self.count is not None and (type(self.count) is not int or self.count < 0):
            raise ValueError("reserve count must be unknown or a nonnegative integer")
        if type(self.hud_visible) is not bool or type(self.reviewed) is not bool:
            raise ValueError("explicit review and visibility required")


def reserve_support(before: ReserveObservation, after: ReserveObservation,
                    *, max_gap: float) -> dict:
    """Return ambiguous supporting evidence, never START/SELF/terminal permission.

    max_gap is a frozen trial parameter, not an established Robotron threshold.
    The caller retains both source observations. Duplicate pixels cannot supply
    independent temporal corroboration even under a new observation identifier.
    """
    if type(max_gap) not in (float, int) or not math.isfinite(max_gap) or max_gap <= 0:
        raise ValueError("positive finite maximum comparison gap required")
    result = dict(status='unknown', support=None, game_over=False,
                  self_confirmed=False, restart_authorized=False,
                  observations=[before.observation_id, after.observation_id])
    if (before.episode != after.episode or before.channel != after.channel
            or before.observation_id == after.observation_id
            or before.source_sha256 == after.source_sha256
            or not 0 < after.timestamp - before.timestamp <= max_gap
            or not all(o.reviewed and o.hud_visible and o.count is not None
                       for o in (before, after))):
        return result
    delta = after.count - before.count
    result['status'] = 'reviewed_support_only'
    result['reserve_delta'] = delta
    result['final_active_life_possible'] = after.count == 0
    result['support'] = ('reserve_decrement_possible_death_or_respawn' if delta == -1
                         else 'reserve_increase_possible_bonus_or_new_game' if delta > 0
                         else 'multiple_losses_or_discontinuity' if delta < -1
                         else 'unchanged_reserves')
    return result
