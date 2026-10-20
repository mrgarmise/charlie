"""Robotron BODY control adapter for generic agency inference."""
import time
import math

from .agency import AgencyTracker
from .projectile_agency import ShotOrigins
from .eyes.tracking import SpriteTracker
from .models import Action

VECTORS = {'E': (1, 0), 'W': (-1, 0), 'S': (0, 1), 'N': (0, -1),
           'NE': (1, -1), 'SE': (1, 1), 'NW': (-1, -1), 'SW': (-1, 1),
           'STAY': (0, 0)}


class VisualAgency:
    """Track every visible region, independent of its taught identity."""
    def __init__(self, *, bootstrap_body_fire=False, projectile_confirmation=False):
        self.bootstrap_body_fire = bootstrap_body_fire
        self.projectile_confirmation = projectile_confirmation
        self.shots = ShotOrigins()
        self.spawn_prior = True
        self.expected_self = None
        self.tracker = SpriteTracker()
        self.agency = AgencyTracker()
        self.tick = 0
        self.pairs = []
        self.positions = {}
        self.assignments = {}

    def observe(self, pairs, move=None, interval_seconds=None, *, observed_at=None, reference_positions=None):
        self.pairs = pairs
        tracking_started = time.perf_counter()
        assignments = self.tracker.update(self.tick, [d for d, _ in pairs], observed_at=observed_at)
        self.tracker.last_update["processing_seconds"] = time.perf_counter()-tracking_started
        self.assignments = assignments
        self.tick += 1
        self.positions = {track: tuple(pairs[index][0].center) for index, track in assignments.items()}
        lineage = []
        prior_id = self.agency.last_confirmed_id
        if prior_id is not None and prior_id not in self.positions:
            prior = next((row for row in self.tracker.last_update["predictions"]
                          if row["track_id"] == prior_id), None)
            if prior:
                created = [event["track_id"] for event in self.tracker.last_update["events"]
                           if event["kind"] == "created"]
                nearby = [track_id for track_id in created
                          if sum((self.positions[track_id][i]-prior["predicted"][i])**2
                                 for i in (0,1)) <= self.tracker.max_distance**2]
                if len(nearby) == 1 and self.agency.propose_successor(prior_id,nearby[0]):
                    lineage.append({"from_track_id":prior_id, "to_track_id":nearby[0],
                                    "status":"proposal_requires_new_direct_response"})
        if move is not None:self.spawn_prior=False
        prior={key:math.exp(-sum((v-50.)**2 for v in p)/(2*15.**2))
               for key,p in self.positions.items()} if self.spawn_prior else {}
        previous_self = self.agency.self_id
        snapshot = self.agency.observe(self.positions, VECTORS[move] if move is not None else None,
                                   interval_seconds=interval_seconds, reference_positions=reference_positions, candidate_prior=prior)
        shot_id = self.shots.confirmed
        contradicted=any(row['track_id']==shot_id and row['reason'] in
            ('wrong_way','nonresponse_or_off_axis','continued_during_neutral') for row in snapshot['evidence'])
        retained_occlusion=(observed_at is not None and self.brief_occlusion(observed_at))
        if ((shot_id not in self.positions and not retained_occlusion) or snapshot.get('global_motion') or contradicted
                or (shot_id in self.tracker.active and self.tracker.active[shot_id].identity_uncertain)):
            self.shots.confirmed = None
            if shot_id is not None or snapshot.get('global_motion'):self.shots.votes.clear()
        if self.projectile_confirmation and self.shots.confirmed is not None:
            self.agency.self_id = self.shots.confirmed
            self.agency.last_confirmed_id = self.shots.confirmed
            snapshot['self_track_id'] = self.shots.confirmed
            snapshot['confirmation_route'] = 'two_nonparallel_command_aligned_shot_origins'
            snapshot['event'] = 'acquired' if previous_self != self.shots.confirmed else None
            snapshot['projectile_support'] = self.shots.votes.get(self.shots.confirmed,[])
        for row in self.tracker.last_update["detections"]:
            row["class_scores"] = dict(pairs[row["index"]][1].get("class_scores", {}))
        if self.expected_self is not None:
            self.expected_self=dict(self.expected_self,status='confirmed' if self.agency.self_id is not None else
                'provisional' if self.positions else 'expected',candidate_track_id=snapshot.get('candidate_track_id'))
        snapshot["self_visibility"] = "observed" if self.controlled_track_id in self.positions else "missing; controls require an observed position"
        snapshot["expected_self"] = self.expected_self
        snapshot["spawn_prior"] = dict(weights={str(k):v for k,v in prior.items()}, interpretation="candidate ranking only; no causal confidence")
        snapshot["tracking"] = self.tracker.last_update
        snapshot["lineage_proposals"] = lineage
        snapshot["controlled_track_id"] = self.controlled_track_id
        snapshot["identity_status"] = ("confirmed" if self.agency.self_id is not None else
                                       "provisional" if self.controlled_track_id is not None else "unknown")
        return snapshot

    def reframe(self):
        """New camera coordinates invalidate association, never recycle IDs."""
        retired=list(self.tracker.active)
        self.tracker.finished.extend(self.tracker.active.values())
        self.tracker.active.clear()
        self.agency=AgencyTracker()
        self.shots.reset()
        self.expected_self=None
        self.spawn_prior=False
        self.positions={};self.assignments={};self.pairs=[]
        return retired

    def confirmed_respawn(self, *, death_confirmed, respawn_confirmed, game_over=False):
        """Accept independently established life evidence, never infer it from SELF loss."""
        if not death_confirmed or not respawn_confirmed or game_over:
            return False
        self.reframe()
        self.spawn_prior=True
        return True

    def seed_new_game(self,transport,observations):
        """Expected spawn only after acknowledged START and fresh visual commencement."""
        ack=(transport or {}).get('ack_at')
        rows=list(observations[-3:])
        if len(rows)<3 or any((r.get('screen_state') or r).get('phase')!='gameplay' for r in rows):return False
        stamps=[r.get('capture_timestamp') for r in rows]
        if ((transport or {}).get('command')!='START' or (transport or {}).get('accepted') is not True or not isinstance(ack,(float,int))
                or isinstance(ack,bool) or not math.isfinite(ack) or len(stamps)<3
                or any(not isinstance(t,(float,int)) or isinstance(t,bool) or not math.isfinite(t) for t in stamps)
                or not all(b>a for a,b in zip(stamps,stamps[1:])) or stamps[0]<=ack):return False
        self.spawn_prior=True
        self.expected_self=dict(status='expected',center=[50.,50.],basis='acknowledged START plus fresh visual commencement')
        return True

    def brief_occlusion(self,at):
        key=self.agency.last_confirmed_id
        track=self.tracker.active.get(key)
        belief=self.agency.beliefs.get(key)
        return bool(key not in self.positions and track and belief and 0<belief.misses<=2
                    and track.last_time is not None and 0<=at-track.last_time<=.25)

    @property
    def controlled_track_id(self):
        if self.agency.self_id is not None:
            return self.agency.self_id
        if not self.bootstrap_body_fire or self.agency.last_snapshot.get('global_motion'):
            return None
        leader = self.agency.last_snapshot.get('candidate_track_id')
        belief = self.agency.beliefs.get(leader)
        if (leader in self.positions and belief and belief.hits >= 2
                and len(belief.directions) >= 2 and belief.contradictions == 0
                and belief.confidence-self.agency.last_snapshot.get('runner_up_confidence',0)
                    >= self.agency.separation):
            return leader
        return None

    @property
    def player(self):
        return self.positions.get(self.controlled_track_id)

    def discover(self, read_pairs, controller, *, pulse_ms=60, deadline=None, record=None, observation_time=None, response_frames=2, should_stop=None, center_spawn=None, fire_first=True, capture_shots=None, fire_ms=None):
        """Fire-first shot evidence, then bounded movement/neutral fallback.

        fire_first=False and center_spawn=False permit exact replay of historic
        movement-only recordings; they never create new observations or controls.

        Controller.execute centers both sticks at each pulse's end. Read the
        two fresh post-pulse exposures, measuring displacement from the pre-pulse
        reference to the second endpoint, then an independent neutral interval.
        The intermediate exposure is retained without scoring an early response.
        """
        if fire_ms is not None and not 30<=fire_ms<=400:raise ValueError('fire_ms must be 30..400; no hold lease extension')
        accept_exposure=getattr(read_pairs,'accept_exposure',None)
        if center_spawn is not None:self.spawn_prior=bool(center_spawn)
        self.last_discovery = dict(schema='causal-discovery-result-v1', commands=[], capture_timestamps=[],
                                   confirmed_self=False, complete=False,
                                   spawn_prior='center candidate ordering only; causal evidence required' if center_spawn or self.spawn_prior else None)
        if self.spawn_prior:
            original_read=read_pairs
            def read_pairs():
                pairs=original_read()
                read_pairs.projectiles=getattr(original_read,'projectiles',[])
                return sorted(pairs,key=lambda pair:sum((float(v)-50.)**2 for v in pair[0].center))
        if response_frames not in (2, 3):
            raise ValueError('agency response window must contain two or three fresh frames')
        def stopped():
            return ((deadline is not None and time.monotonic() >= deadline)
                    or (should_stop is not None and should_stop()))
        if stopped():return self.player
        if self.agency.self_id is None:self.shots.reset()
        pairs = read_pairs()
        initial = self.observe(pairs, observed_at=observation_time() if observation_time else time.monotonic())
        self.last_discovery['capture_timestamps'].append(self.tracker.last_update['observed_at'])
        if record:
            record(initial)  # pre-command detections are essential for exact replay
        if stopped():return self.player
        if self.agency.self_id is not None and self.player is not None:
            self.last_discovery['confirmed_self']=True
            return self.player
        # Fire first in two nonparallel directions. Missing acknowledged timing
        # or missing projectile observations supplies no causal evidence.
        for fire in (('E','N') if fire_first else ()):
            if stopped():return self.player
            if deadline is not None and time.monotonic()+pulse_ms/1000 >= deadline:return self.player
            baseline=list(getattr(read_pairs,'projectiles',[]))
            bodies=dict(self.positions)
            duration=fire_ms if fire_ms is not None else pulse_ms
            if capture_shots is not None and deadline is not None and time.monotonic()+duration/1000+.25>=deadline:break
            if capture_shots is not None:
                execution,packets,capture_status=capture_shots(controller,
                    Action('STAY',fire,'shot-origin acquisition'),duration,deadline,should_stop)
                self.last_discovery.setdefault('shot_capture',[]).append(capture_status)
                self.shots.begin(VECTORS[fire],execution,bodies,baseline)
                for endpoint,packet in enumerate(packets,1):
                    pairs=accept_exposure(packet)
                    if pairs is None:continue # already recorded baseline, never replayed twice
                    at=packet.at
                    evidence=self.shots.observe(getattr(accept_exposure,'projectiles',[]),at)
                    snapshot=self.observe(pairs,observed_at=at)
                    snapshot.update(phase='shot_origin_experiment',shot_evidence=evidence,
                        projectile_candidate=self.shots.confirmed,projectile_confirmation_enabled=self.projectile_confirmation,
                        capture_window=capture_status,control_execution=execution,
                        actuators=dict(body='STAY',fire=fire,endpoint=endpoint))
                    self.last_discovery['capture_timestamps'].append(at)
                    if record:record(snapshot)
                if self.agency.self_id is not None and self.player is not None:
                    self.last_discovery['confirmed_self']=True
                    return self.player
            else:
                controller.execute(Action('STAY',fire,'shot-origin acquisition'),pulse_ms)
                execution=getattr(controller,'last_execution',None) or {}
                self.shots.begin(VECTORS[fire],execution,bodies,baseline)
                for endpoint in range(3):
                    if stopped():return self.player
                    pairs=read_pairs()
                    at=observation_time() if observation_time else time.monotonic()
                    evidence=self.shots.observe(getattr(read_pairs,'projectiles',[]),at)
                    snapshot=self.observe(pairs,observed_at=at)
                    snapshot.update(phase='shot_origin_experiment',shot_evidence=evidence,
                        projectile_candidate=getattr(self.shots,'confirmed',None),
                        projectile_confirmation_enabled=self.projectile_confirmation,
                        actuators=dict(body='STAY',fire=fire,endpoint=endpoint+1))
                    self.last_discovery['capture_timestamps'].append(at)
                    if record:record(snapshot)
                    if self.agency.self_id is not None and self.player is not None:
                        self.last_discovery['confirmed_self']=True
                        return self.player
        for probe, move in enumerate(('E', 'W', 'S', 'N', 'E', 'W')):
            if stopped():break
            if deadline is not None and time.monotonic() + 2*pulse_ms/1000 >= deadline:
                break
            # A bounded probe can precede a new region appearing after respawn;
            # absence of a track never fabricates a signed response.
            for direction in (move, 'STAY'):
                if stopped():return self.player
                if deadline is not None and time.monotonic() + pulse_ms/1000 >= deadline:
                    return self.player
                origin = dict(self.positions)
                origin_at = self.tracker.last_update['observed_at']
                start = time.monotonic()
                fire = ('N','E','S','W','N','E')[probe] if self.bootstrap_body_fire and direction != 'STAY' else 'NONE'
                controller.execute(Action(direction, fire, 'agency discovery'), pulse_ms)
                pairs = read_pairs()
                at = observation_time() if observation_time else time.monotonic()
                if direction != 'STAY':
                    # Fresh sensor exposure does not guarantee the TV has yet
                    # rendered the action. Preserve the early frame, associating
                    # exactly once, but withhold agency judgment until the declared
                    # final endpoint. The reference remains the pre-pulse view.
                    for endpoint in range(1, response_frames):
                        early = self.observe(pairs, observed_at=at)
                        early['phase'] = 'response_window_early_unmeasured'
                        early['actuators'] = {'body':direction, 'fire':fire}
                        early['response_window'] = {'origin_at': origin_at, 'move': direction,
                                                    'endpoint': endpoint, 'endpoints': response_frames}
                        if record:
                            record(early)
                        if stopped():return self.player
                        pairs = read_pairs()
                        at = observation_time() if observation_time else time.monotonic()
                snapshot = self.observe(pairs, direction, time.monotonic()-start,
                                        observed_at=at,
                                        reference_positions=origin if direction != 'STAY' else None)
                self.last_discovery['commands'].append(direction)
                self.last_discovery['capture_timestamps'].append(at)
                snapshot['actuators'] = {'body':direction, 'fire':fire, 'pulse_ms':pulse_ms}
                if direction != 'STAY':
                    snapshot['phase'] = 'action_response_window'
                    snapshot['response_window'] = {'origin_at': origin_at, 'endpoint_at': at,
                                                    'move': direction, 'endpoint': response_frames, 'endpoints': response_frames,
                                                    'duration_seconds': at-origin_at}
                if record:
                    record(snapshot)
            if self.agency.self_id is not None and self.player is not None:
                break
        self.last_discovery['confirmed_self'] = self.agency.self_id is not None
        times = self.last_discovery['capture_timestamps']
        commands = self.last_discovery['commands']
        self.last_discovery['complete'] = (all(x in commands for x in ('E','W','S','N'))
            and commands.count('STAY') >= 4 and len(times) >= 9
            and all(isinstance(t,(float,int)) and math.isfinite(t) for t in times)
            and all(b>a for a,b in zip(times,times[1:])))
        return self.player
