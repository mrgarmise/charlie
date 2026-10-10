"""Best-effort score instrumentation, isolated from the control thread."""
from __future__ import annotations
import json
import queue
import threading
import time
from .robotron_score_system import RobotronScoreSystem
from .score_events import ScoreEventLog


class ScoreObserver:
    def __init__(self, calibration, path):
        self.system = RobotronScoreSystem(calibration, self_channel=1, confirm_baseline=True)
        self.log = ScoreEventLog(path)
        self.queue = queue.Queue(maxsize=2)
        self.dropped = 0
        self.costs = []
        self.errors = 0
        self.frames = []
        self.latest_frame = None
        self.final_observation = None
        self.late_change_frames = 0
        self.omitted_change_frames = 0
        self.accepted_confidence = {1:None, 2:None}
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def reframe(self,calibration):
        # FIFO changes reader geometry between old/new observations. Preserve
        # game score history; a viewpoint change is not a new game/reset.
        self.queue.put(('geometry',calibration),timeout=1.)

    def submit(self, frame, *, timestamp, sample, preceding_action,observation_id=None):
        begin = time.monotonic()
        if self.queue.full():
            self.dropped += 1
            return
        # Independent pixels: camera buffers may be reused by the next capture.
        try:
            copied = frame.copy()
            self.queue.put_nowait((copied, timestamp, sample, preceding_action,
                                  time.monotonic()-begin,observation_id))
        except Exception:
            self.errors += 1

    def _run(self):
        while True:
            item = self.queue.get()
            try:
                if item is None:
                    return
                if len(item)==2 and item[0]=='geometry':
                    self.system.reader.calibration=item[1]
                    continue
                frame, timestamp, sample, action, copy_seconds, observation_id = item
                begin = time.monotonic()
                error = None
                try:
                    channels = self.system.observe(frame, t=timestamp)
                except Exception as exc:
                    self.errors += 1
                    error = f'{type(exc).__name__}: {exc}'
                    channels = self.system.tracker.tracker.observe(
                        None, None, player1_confidence=0., player2_confidence=0.)
                    self.system.latest = channels
                elapsed = time.monotonic()-begin
                self.costs.append(elapsed)
                # Build the canonical score evidence without a second disk write.
                row = self._row(channels, timestamp)
                for player, observation in ((1, channels.player1), (2, channels.player2)):
                    if observation.status in ('baseline', 'changed'):
                        self.accepted_confidence[player] = observation.confidence
                    row[f'p{player}']['accepted_confidence'] = self.accepted_confidence[player]
                name = f'score-raw-{sample:04d}.png'
                self.latest_frame = (name, frame)
                changed = channels.player1.changed or channels.player2.changed
                initial = sample <= 16
                if initial or (changed and self.late_change_frames < 16):
                    if not initial:
                        self.late_change_frames += 1
                    self.frames.append((name, frame))
                    row['raw_frame'] = name
                elif changed:
                    self.omitted_change_frames += 1
                row.update(sample=sample, timestamp=timestamp, preceding_action=action,observation_id=observation_id,
                           processing_seconds=elapsed, enqueue_copy_seconds=copy_seconds,
                           error=error, reward_evidence=channels.self_delta,
                           attribution='temporal_association_only')
                # The final image is retained at close even when this row did
                # not trigger retention. Bind it explicitly without rewriting
                # the append-only historical score row.
                self.final_observation = dict(sample=sample, timestamp=timestamp,observation_id=observation_id,
                    raw_frame=name, observed_score=channels.player1.observed_score,
                    retained_score=channels.player1.score,
                    status=channels.player1.status, error=error)
                with self.log.path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(row)+'\n')
                for player, observation in ((1, channels.player1), (2, channels.player2)):
                    if observation.changed:
                        print(f'SCORE: P{player}={observation.score} Δ=+{observation.delta} confidence={observation.confidence:.2f}')
            except Exception:
                # Instrumentation and its output must never terminate gameplay.
                self.errors += 1
            finally:
                self.queue.task_done()

    @staticmethod
    def _row(channels, timestamp):
        return {'t':timestamp, 'p1':{**vars(channels.player1), 'observed':channels.player1.observed_score},
                'p2':{**vars(channels.player2), 'observed':channels.player2.observed_score},
                'self_channel':channels.self_channel, 'self_score':channels.self_score,
                'self_delta':channels.self_delta}

    def close(self):
        # Called only after camera and controls have closed.
        try:
            self.queue.put(None, timeout=.1)
        except queue.Full:
            return
        self.thread.join(timeout=5.)
        if not self.thread.is_alive() and self.latest_frame is not None:
            if all(name != self.latest_frame[0] for name, _ in self.frames):
                self.frames.append(self.latest_frame)

    @staticmethod
    def queue_game(journal, root, *, session, number, interrupted=False, synthetic=False):
        """Append a game attempt to the existing diary; never certify its score.

        This is called before and after the game child, without human interaction.
        An interrupted/missing report remains an inspectable immutable record.
        """
        from pathlib import Path
        import hashlib,math
        from memory.evidence import digest
        root=Path(root).resolve()
        attempt='score-attempt:'+digest(dict(session=str(session),number=number))
        old=[r for r in journal.category_records('observation','score_game_record')
             if r.data['payload']['attempt_id']==attempt]
        deficiencies=[];report={};report_hash=None;origin={}
        try:
            raw=(root/'report.json').read_bytes();report=json.loads(raw)
            if not isinstance(report,dict):raise ValueError('report object required')
            report_hash=hashlib.sha256(raw).hexdigest()
        except (OSError,ValueError) as exc:
            report={};deficiencies.append('Report unavailable: '+str(exc))
        try:origin=json.loads((root/'capture-origin.json').read_text())
        except (OSError,ValueError):pass
        source_episode=origin.get('capture_id') or attempt
        if report_hash:source_episode='episode:'+report_hash
        capture_key=origin.get('capture_id') or attempt
        summary=report.get('score_summary') or {};boundary=report.get('episode_end') or {}
        terminal_times=(boundary.get('evidence') or {}).get('terminal_capture_timestamps',[])
        observations=[]
        try:
            with (root/'score.jsonl').open() as stream:
                for line,text in enumerate(stream,1):
                    try:
                        row=json.loads(text)
                        if row.get('raw_frame'):observations.append(dict(row,line=line))
                        observations=observations[-64:]
                    except (ValueError,AttributeError):deficiencies.append('Unreadable score row '+str(line))
        except OSError:pass
        final=summary.get('final_observation')
        if isinstance(final,dict) and final.get('raw_frame'):
            match=next((r for r in reversed(observations) if r.get('sample')==final.get('sample')),None)
            if not match:observations.append(dict(final,p1=dict(observed_score=final.get('observed_score'),confidence=final.get('confidence',0))))
        selected=None;artifact=None
        # Prefer score observations actually bound to the terminal sequence.
        ordered=sorted(observations,key=lambda r:r.get('timestamp') in terminal_times)
        for row in reversed(ordered):
            name=row.get('raw_frame')
            if not isinstance(name,str):continue
            path=(root/name).resolve()
            if not path.is_relative_to(root):deficiencies.append('Frame escapes original capture');continue
            try:
                from PIL import Image
                with Image.open(path) as image:image.verify()
                artifact=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            except (OSError,ValueError):continue
            selected=row;break
        proposal=None
        if selected:
            at=selected.get('timestamp',selected.get('t'));channel=selected.get('p1') or {}
            value=channel.get('observed_score',channel.get('observed'));confidence=channel.get('confidence',0)
            if type(value) is not int or value<0:value=None
            if type(confidence) not in (int,float) or not math.isfinite(confidence) or not 0<=confidence<=1:confidence=0
            if type(at) in (int,float) and math.isfinite(at) and at>=0:
                source=journal.append('observation',dict(category='score_review_source',artifact=artifact,
                    camera_observation_id=selected.get('observation_id'),score_row=selected,
                    score_log_sha256=hashlib.sha256((root/'score.jsonl').read_bytes()).hexdigest() if (root/'score.jsonl').exists() else None),
                    episode=source_episode,at=at,producer='ScoreObserver',version='deferred-review-v1')
                proposal=ScoreObserver.review_proposal(journal,artifact['path'],source_episode=source_episode,
                    timestamp=at,clock='original camera capture monotonic',source_id=source.id,
                    proposed=value,confidence=confidence,synthetic=synthetic or report.get('simulation',False),
                    context=dict(source_session=str(session),reader_revision=(report.get('provenance') or {}).get('code_revision'),
                        capture_key=capture_key,terminal_support=at in terminal_times and boundary.get('confirmed') is True))
            else:deficiencies.append('Original capture timestamp unavailable')
        else:deficiencies.append('Original readable image unavailable')
        timing=report.get('session_timing') or {}
        payload=dict(category='score_game_record',attempt_id=attempt,capture_key=capture_key,
            session=str(session),number=number,source_root=str(root),source_episode=source_episode,
            report_sha256=report_hash,proposal_id=proposal.id if proposal else None,artifact=artifact,
            reported_score=summary.get('self_score',report.get('score')),reader_status=summary.get('status','unmeasured'),
            start_timestamp=timing.get('started_at'),end_timestamp=timing.get('stopped_at'),
            provenance=report.get('provenance',{}),policy=report.get('planning_mode','unknown'),
            configuration={k:report.get(k) for k in ('seconds','pulse_ms','armed','learned_semantics')},
            result=report.get('result','interrupted' if interrupted else 'awaiting report'),
            boundary=boundary,complete_game_claim=boundary.get('confirmed') is True,
            synthetic=synthetic or report.get('simulation',False),deficiencies=deficiencies,
            previous=old[-1].id if old else None,physical_authorization=False,
            qualification='reported attempt only; no independent complete-game score certificate')
        if old and all(old[-1].data['payload'].get(k)==v for k,v in payload.items() if k!='previous'):return old[-1]
        return journal.append('observation',payload,episode=source_episode,
            sources=[proposal.id] if proposal else [],producer='ScoreObserver',version='deferred-review-v1')

    @staticmethod
    def review_proposal(journal,frame,*,source_episode,timestamp,clock,proposed,confidence,
                        source_id=None,context=None,partition='diagnostic',synthetic=False):
        """Immutable score proposal for existing offline inspection; never a certificate."""
        import hashlib,math
        from pathlib import Path
        frame=Path(frame).resolve()
        if not source_episode or not clock or not math.isfinite(timestamp) or timestamp<0:
            raise ValueError('original source identity, timestamp and clock required')
        if proposed is not None and (type(proposed) is not int or proposed<0):raise ValueError('invalid proposed score')
        if not math.isfinite(confidence) or not 0<=confidence<=1:raise ValueError('invalid confidence')
        if partition not in ('training','validation','final','diagnostic'):raise ValueError('invalid image partition')
        from PIL import Image
        with Image.open(frame) as original:original.verify()
        artifact_hash=hashlib.sha256(frame.read_bytes()).hexdigest()
        rows=journal.category_records('observation','score_review_proposal')
        if any((r.data['payload']['source_episode']==source_episode or r.data['payload']['artifact']['sha256']==artifact_hash
                or ((context or {}).get('source_session') and r.data['payload'].get('context',{}).get('source_session')==(context or {}).get('source_session')))
                and r.data['payload']['partition']!=partition for r in rows):
            raise ValueError('one source game/session cannot cross score training/validation/final partitions')
        if source_id:
            source=journal.get(source_id)
            if source.data['episode']!=source_episode or source.data['at']!=timestamp:
                raise ValueError('score proposal must bind exact original source time/episode')
        return journal.append('observation',dict(category='score_review_proposal',schema='score-human-review-v1',
            artifact=dict(path=str(frame),sha256=artifact_hash),
            source_episode=source_episode,timestamp=timestamp,clock=clock,proposed_score=proposed,
            confidence=confidence,context=context or {},partition=partition,synthetic=synthetic,
            timestamp_provenance='exact original journal source' if source_id else 'operator-supplied source metadata; not independently qualified',
            qualification='unqualified proposal; no complete-game or reader-accuracy certificate'),
            episode=source_episode,at=timestamp,sources=[source_id] if source_id else [],producer='ScoreObserver',version='human-review-v1')

    @staticmethod
    def annotate_review(journal,proposal_id,*,annotator,verdict,value=None,reason,independent=False,supersedes=None):
        import hashlib
        from datetime import datetime,timezone
        from pathlib import Path
        row=journal.get(proposal_id);p=row.data['payload']
        if p.get('category')!='score_review_proposal' or not annotator.strip() or not reason.strip():
            raise ValueError('original score proposal, annotator and rationale required')
        if hashlib.sha256(Path(p['artifact']['path']).read_bytes()).hexdigest()!=p['artifact']['sha256']:
            raise ValueError('original score image changed')
        if verdict=='confirm':value=p['proposed_score']
        elif verdict=='unreadable':value=None
        elif verdict!='correct':raise ValueError('confirm, correct or unreadable required')
        if verdict!='unreadable' and (type(value) is not int or value<0):raise ValueError('readable annotation requires exact nonnegative digits')
        if supersedes:
            prior=journal.get(supersedes).data['payload']
            if prior.get('category')!='score_human_annotation' or prior.get('proposal_id')!=proposal_id or prior.get('annotator')!=annotator:
                raise ValueError('correction must supersede this reviewer and proposal')
        return journal.append('observation',dict(category='score_human_annotation',proposal_id=proposal_id,
            annotator=annotator,verdict=verdict,value=value,reason=reason,independence_attested=bool(independent),
            reviewed_at=datetime.now(timezone.utc).isoformat(),artifact_sha256=p['artifact']['sha256'],
            source_episode=p['source_episode'],timestamp=p['timestamp'],partition=p['partition'],synthetic=p['synthetic'],
            supersedes=supersedes,qualification='human annotation; complete-game boundary and independent qualification still required'),
            episode=row.data['episode'],sources=[proposal_id],producer='human-score-review',version='1')

    @staticmethod
    def review_metrics(journal,*,partition='final'):
        import math
        proposals={r.id:r.data['payload'] for r in journal.category_records('observation','score_review_proposal')
                   if r.data['payload']['partition']==partition and not r.data['payload']['synthetic']}
        annotations={}
        all_annotations=journal.category_records('observation','score_human_annotation')
        superseded={r.data['payload'].get('supersedes') for r in all_annotations}
        for r in all_annotations:
            if r.id in superseded:continue
            p=r.data['payload']
            if p['proposal_id'] in proposals and p['independence_attested']:
                annotations.setdefault(p['proposal_id'],[]).append(p)
        eligible=correct=accepted=false_confident=abstained=disagreement=unreadable=0
        seen_pixels=set();bins={}
        for key,rows in annotations.items():
            image=proposals[key]['artifact']['sha256']
            if image in seen_pixels:continue
            seen_pixels.add(image)
            duplicates=[k for k in annotations if proposals[k]['artifact']['sha256']==image]
            if len({(proposals[k]['proposed_score'],proposals[k]['confidence'],proposals[k].get('context',{}).get('reader_revision')) for k in duplicates})!=1:
                disagreement+=1;continue
            values={r['value'] for k in duplicates for r in annotations[k]}
            if len(values)!=1:disagreement+=1;continue
            value=next(iter(values))
            if value is None:unreadable+=1;continue
            eligible+=1;p=proposals[key];prediction=p['proposed_score']
            if prediction is None:abstained+=1;continue
            accepted+=1;correct+=int(prediction==value)
            false_confident+=int(prediction!=value and p['confidence']>=.99)
            b=bins.setdefault(min(9,int(p['confidence']*10)),dict(samples=0,confidence_sum=0.,correct=0))
            b['samples']+=1;b['confidence_sum']+=p['confidence'];b['correct']+=int(prediction==value)
        # Wilson interval describes this labeled batch, not independence of adjacent frames.
        if accepted:
            z=1.959963984540054;rate=correct/accepted;d=1+z*z/accepted
            center=(rate+z*z/(2*accepted))/d
            half=z*math.sqrt(rate*(1-rate)/accepted+z*z/(4*accepted*accepted))/d
            interval=[max(0,center-half),min(1,center+half)]
        else:rate=None;interval=None
        return dict(partition=partition,eligible=eligible,accepted=accepted,correct=correct,exact_score_accuracy=rate,
            wilson_95_interval=interval,false_confident_acceptances=false_confident,abstained=abstained,
            abstention_rate=abstained/eligible if eligible else None,coverage=accepted/eligible if eligible else None,
            disputed_proposals=disagreement,unreadable=unreadable,
            qualification='descriptive labeled batch only; source-group independence and reader calibration unverified',
            calibration_bins={str(k):dict(samples=b['samples'],mean_confidence=b['confidence_sum']/b['samples'],
                empirical_accuracy=b['correct']/b['samples']) for k,b in bins.items()},
            distinct_original_images=len(seen_pixels),target_99_supported=False)

    def report(self):
        return {**self.system.report(), 'log':'score.jsonl', 'samples':len(self.costs),
                'dropped_samples':self.dropped, 'errors':self.errors,
                'worker_finished':not self.thread.is_alive(),
                'final_observation':self.final_observation if not self.thread.is_alive() else None,
                'processing_seconds_total':sum(self.costs),
                'processing_seconds_max':max(self.costs, default=0.),
                'raw_frames':[name for name, _ in self.frames],
                'retained_instrumentation_bytes':sum(f.width*f.height*len(f.getbands()) for _,f in self.frames),
                'queue_capacity':2,'queue_occupancy':self.queue.qsize(),
                'raw_frame_retention':'first 16 samples, up to 16 later accepted changes, final sample',
                'omitted_change_frames':self.omitted_change_frames,
                'accepted_confidence':dict(self.accepted_confidence),
                'mode':'observational_background', 'timestamp_clock':'monotonic',
                'metric':'official_game_score', 'policy_feedback':False}
