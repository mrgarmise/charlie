"""Action-contingent identity over generic visual tracks.

Inputs are positions sampled before/after a known BODY control interval. No
sprite classes, board geometry, or enemy rules enter this model. Scores express
accumulated evidence, NOT calibrated probabilities. If multiple processes obey
indistinguishably, identity remains unknown. A caller must supply trustworthy
control/exposure alignment; endpoint samples cannot measure response latency.
"""
from dataclasses import dataclass, field
import math
from statistics import median


@dataclass
class Belief:
    confidence: float = 0.0
    hits: int = 0
    stops: int = 0
    contradictions: int = 0
    directions: set = field(default_factory=set)
    last_direction: tuple | None = None
    reversed: bool = False
    awaiting_stop: bool = False
    misses: int = 0
    indirect_score: float = 0.0
    lineage_source: int | None = None


class AgencyTracker:
    def __init__(self, min_motion=.20, stop_motion=.35, threshold=.72,
                 separation=.18, max_missing=3):
        self.min_motion = min_motion
        self.stop_motion = stop_motion
        self.threshold = threshold
        self.separation = separation
        self.max_missing = max_missing
        self.beliefs = {}
        self.previous = {}
        self.self_id = None
        self.last_confirmed_id = None
        self.last_command = None
        self.last_snapshot = {}
        self.pending_lineage = {}

    def reset(self):
        """Explicit death/world reset. New tracks must earn identity afresh."""
        self.beliefs.clear()
        self.previous.clear()
        self.self_id = None
        self.last_confirmed_id = None
        self.last_command = None
        self.last_snapshot = {}
        self.pending_lineage = {}

    def propose_successor(self, previous_id, successor_id):
        """A bounded prior only; no hits, stops or reversal are inherited.

        The visual caller must supply a unique plausible spatial successor to a
        missing, previously confirmed identity. The prior is consumed only after
        the successor itself obeys a subsequent BODY command.
        """
        prior = self.beliefs.get(previous_id)
        if (previous_id != self.last_confirmed_id or prior is None
                or prior.confidence < self.threshold or successor_id == previous_id):
            return False
        if successor_id in self.pending_lineage or self.beliefs.get(successor_id, Belief()).lineage_source is not None:
            return False
        self.pending_lineage[successor_id] = (previous_id, min(.18, prior.confidence*.2), 3)
        return True

    def observe(self, positions, command=None, *, interval_seconds=None, reference_positions=None):
        """command caused displacement since previous observation; None=unmeasured.

        reference_positions optionally supplies an explicit pre-action window
        origin. IDs absent from the intervening observation are excluded.
        A zero vector denotes a measured neutral interval, not missing control
        data. Missing observations never create displacement across an occlusion.
        Right-stick effects are deliberately excluded by the caller.
        """
        positions = {key: tuple(value) for key, value in positions.items()}
        if command is not None:
            length = math.hypot(*command)
            command = tuple(x / length for x in command) if length else (0., 0.)
        reference = (self.previous if reference_positions is None else
                     {k: v for k, v in reference_positions.items() if k in self.previous})
        displacements = {key: (pos[0]-reference[key][0], pos[1]-reference[key][1])
                         for key, pos in positions.items() if key in reference}
        # A coherent field displacement is not evidence for any particular body.
        global_motion = False
        if len(displacements) >= 3:
            common = tuple(median(v[i] for v in displacements.values()) for i in (0, 1))
            coherent = sum(math.dist(v, common) <= self.stop_motion for v in displacements.values())
            global_motion = math.hypot(*common) >= self.min_motion and coherent / len(displacements) >= .8
        evidence = []
        for key in positions:
            self.beliefs.setdefault(key, Belief()).misses = 0
        for key, belief in list(self.beliefs.items()):
            if key not in positions:
                belief.misses += 1
                if belief.misses > self.max_missing:
                    belief.confidence *= .5
                if belief.misses > self.max_missing + 8:
                    del self.beliefs[key]
                continue
            if global_motion:
                belief.confidence *= .8
                continue
            if key not in displacements or command is None:
                continue
            v = displacements[key]
            magnitude = math.hypot(*v)
            agreement = sum(a*b for a,b in zip(v,command)) / magnitude if magnitude else 0.
            old = belief.confidence
            reason = 'nonresponse'
            if command == (0., 0.):
                # Stillness is informative ONLY for a process that previously moved.
                if (belief.awaiting_stop or key == self.self_id) and magnitude <= self.stop_motion:
                    if belief.awaiting_stop:
                        belief.stops += 1
                    belief.awaiting_stop = False
                    belief.confidence = min(1., belief.confidence + .10)
                    reason = 'command_linked_stop'
                elif magnitude > self.stop_motion:
                    belief.confidence = max(0., belief.confidence - .25)
                    belief.contradictions += 1
                    belief.awaiting_stop = False
                    reason = 'continued_during_neutral'
                    belief.indirect_score = min(1., belief.indirect_score + .15)
            elif magnitude >= self.min_motion and agreement >= .8:
                belief.hits += 1
                belief.awaiting_stop = True
                belief.directions.add(tuple(round(x, 3) for x in command))
                if belief.last_direction and sum(a*b for a,b in zip(command,belief.last_direction)) < -.8:
                    belief.reversed = True
                belief.last_direction = command
                belief.confidence = min(1., belief.confidence + .18)
                reason = 'signed_command_response'
                lineage = self.pending_lineage.pop(key, None)
                if lineage is not None:
                    belief.lineage_source = lineage[0]
                    belief.confidence = min(1., belief.confidence + lineage[1])
                    reason = 'signed_command_response_with_lineage_prior'
            else:
                belief.awaiting_stop = False
                belief.confidence = max(0., belief.confidence - (.30 if agreement < -.3 else .12))
                belief.contradictions += 1
                self.pending_lineage.pop(key, None)
                reason = 'wrong_way' if agreement < -.3 else 'nonresponse_or_off_axis'
            # Exploratory indirect influence: motion toward previously known SELF.
            # This is descriptive evidence, not a learned causal mediation claim.
            if self.self_id in reference and key != self.self_id and magnitude:
                toward = tuple(reference[self.self_id][i]-reference[key][i] for i in (0,1))
                norm = math.hypot(*toward)
                if norm and sum(a*b for a,b in zip(v,toward))/(magnitude*norm) > .8 and agreement < .8:
                    belief.indirect_score = min(1., belief.indirect_score + .1)
            evidence.append({'track_id': key, 'displacement': list(v), 'agreement': agreement,
                             'confidence_before': old, 'confidence': belief.confidence,
                             'reason': reason, 'contradictions': belief.contradictions,
                             'indirect_score': belief.indirect_score,
                             'lineage_source': belief.lineage_source})
        ranked = sorted(self.beliefs, key=lambda k: self.beliefs[k].confidence, reverse=True)
        leader = ranked[0] if ranked else None
        runner = ranked[1] if len(ranked) > 1 else None
        top = self.beliefs.get(leader)
        second = self.beliefs[runner].confidence if runner is not None else 0.
        old_self = self.self_id
        qualified = (not global_motion and top and top.confidence >= self.threshold and top.hits >= 3
                     and len(top.directions) >= 2 and top.stops >= 2 and top.reversed
                     and top.misses <= self.max_missing
                     and top.confidence-second >= self.separation)
        self.self_id = leader if qualified else None
        event = None
        if self.self_id is not None and self.self_id != old_self:
            event = 'acquired' if self.last_confirmed_id is None else 'reacquired'
        elif old_self is not None and self.self_id is None:
            event = 'lost'
        if self.self_id is not None:
            self.last_confirmed_id = self.self_id
        for key,(source,prior,remaining) in list(self.pending_lineage.items()):
            if remaining <= 1 or source in positions:
                del self.pending_lineage[key]
            else:
                self.pending_lineage[key] = (source,prior,remaining-1)
        self.previous = positions
        self.last_command = command
        self.last_snapshot = {'self_track_id': self.self_id, 'confidence': top.confidence if top else 0.,
                              'candidate_track_id': leader, 'runner_up_track_id': runner,
                              'runner_up_confidence': second, 'event': event,
                              'command': list(command) if command is not None else None,
                              'interval_seconds': interval_seconds, 'latency_seconds': None,
                              'global_motion': global_motion, 'evidence': evidence}
        if reference_positions is not None:
            self.last_snapshot["response_reference_positions"] = {str(k): list(v) for k,v in reference.items()}
        return self.last_snapshot
