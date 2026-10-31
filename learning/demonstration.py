"""Bounded operator ability, driven by the application's existing attention loop.

No camera, controller, Executive, scheduler or HTTP process is created here.
SQLite preserves request/recovery receipts; sensory evidence stays in its normal journal.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import fcntl
import os
import json
from pathlib import Path
import secrets
import platform
import sqlite3
import threading
import time
from uuid import uuid4, UUID

ABILITY = 'demonstrate-object-identification'
TERMINAL = {'completed', 'cancelled', 'failed', 'unavailable'}


def utc():
    return datetime.now(timezone.utc).isoformat()


class Demonstration:
    def __init__(self, attention, factory, state, *, clock=time.monotonic):
        self.attention, self.factory, self.clock = attention, factory, clock
        self.lock = threading.RLock()
        self.boot = uuid4().hex
        self.active = self.pipeline = None
        self.started = self.last_frame = None
        self.challenges = {}
        self.cancel_requested = False
        self.record_error = None
        self.terminal = None
        path = Path(state)/'operator-demonstrations.sqlite3'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.owner_fd=os.open(path.with_suffix('.lock'),os.O_CREAT|os.O_RDWR,0o600)
        try:fcntl.flock(self.owner_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BaseException:
            os.close(self.owner_fd)
            raise RuntimeError('another application owns operator demonstrations')
        self.db = sqlite3.connect(path, check_same_thread=False)
        os.chmod(path,0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, session TEXT, body TEXT, sha256 TEXT)')
        for identifier, raw in self.db.execute('SELECT id,body FROM sessions').fetchall():
            row = json.loads(raw)
            if row['state'] not in TERMINAL:
                row.update(state='cancelled', reason='application_restarted; never replayed', ended_utc=utc())
                self._save(row)
        attention.demonstration = self

    @property
    def running(self):
        return self.active is not None and self.active['state'] == 'running'

    def _save(self, row, event=None):
        body = json.dumps(row, sort_keys=True, allow_nan=False)
        self.db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?)', (row['id'], body))
        detail = json.dumps(dict(utc=utc(), boot=self.boot, session=row['id'],
            state=row['state'], event=event or dict(reason=row.get('reason'))), sort_keys=True, allow_nan=False)
        self.db.execute('INSERT INTO events(session,body,sha256) VALUES (?,?,?)',
                        (row['id'], detail, hashlib.sha256(detail.encode()).hexdigest()))
        self.db.commit()

    def status(self):
        with self.lock:
            now = self.clock()
            self.challenges = {k:v for k,v in self.challenges.items() if now-v < 30}
            if len(self.challenges) >= 64:self.challenges.pop(next(iter(self.challenges)))
            nonce = secrets.token_urlsafe(24)
            self.challenges[nonce] = now
            reason = self.attention.demonstration_unavailable()
            if self.attention.object_labels is None:reason = 'object_label_display_not_enabled'
            if self.record_error:reason = self.record_error
            recent = [json.loads(r[0]) for r in self.db.execute('SELECT body FROM sessions ORDER BY rowid DESC LIMIT 10')]
            return dict(ability=ABILITY, boot=self.boot, nonce=nonce, nonce_valid_seconds=30,
                available=not reason and self.active is None, reason=reason or ('request_in_progress' if self.active else None),
                session=json.loads(json.dumps(self.active)) if self.active else (self.terminal or (recent[0] if recent else None)), recent=recent,
                motion_authorized=False, physical_display='unobserved')

    def submit(self, request):
        with self.lock:
            if self.record_error:raise ValueError('evidence persistence unavailable; restart after repair')
            if not isinstance(request, dict):raise ValueError('request object required')
            if set(request) != {'id','ability','camera','duration','boot','nonce','action'}:
                raise ValueError('exact bounded ability request required')
            if (request['ability'] != ABILITY or request['camera'] != 'pi-primary'
                    or type(request['duration']) is not int or request['duration'] != 15
                    or request['action'] not in ('start','cancel')):
                raise ValueError('only stationary Pi object demonstration for 15 seconds is supported')
            if not isinstance(request['id'], str) or str(UUID(request['id'])) != request['id']:
                raise ValueError('canonical request UUID required')
            if not isinstance(request['nonce'], str):raise ValueError('nonce required')
            issued = self.challenges.pop(request['nonce'], None)
            if request['boot'] != self.boot or issued is None or not 0 <= self.clock()-issued < 30:
                raise ValueError('stale, foreign-boot or replayed request')
            if request['action'] == 'cancel':
                if self.active is None or self.active['id'] != request['id']:
                    raise ValueError('no matching active request')
                self.cancel_requested = True
                self.active['cancellation_requested'] = True
                self._save(self.active)
                return dict(self.active)
            if self.db.execute('SELECT 1 FROM sessions WHERE id=?',(request['id'],)).fetchone():
                raise ValueError('duplicate request ID')
            if self.active is not None:raise ValueError('another demonstration is already requested or running')
            self.active = dict(id=request['id'], execution_id=uuid4().hex, boot=self.boot,
                ability=ABILITY, camera='pi-primary', duration=15, state='requested', requested_utc=utc(),
                requested_at=self.clock(), observations=0, objects=0, display_acknowledgments=0,
                physical_display='unobserved', motion_authorized=False,
                environment=dict(machine=platform.machine(),system=platform.system(),python=platform.python_version()),
                firmware_identity='not independently read back',
                evidence_database='mobile-evidence.sqlite3', events_database='operator-demonstrations.sqlite3')
            self.cancel_requested = False
            self._save(self.active)
            self.attention.bus.emit('operator_demonstration', self.active['id'])
            return dict(self.active)

    def begin(self, identifier):
        with self.lock:
            if self.active is None or self.active['id'] != identifier or self.running:return
            reason = self.attention.demonstration_unavailable()
            if self.cancel_requested:return self.finish('cancelled','operator_cancelled_before_start')
            if self.clock()-self.active['requested_at'] >= 30:reason='request_expired_before_dispatch'
            if self.attention.object_labels is None:reason='object_label_display_not_enabled'
            if reason:return self.finish('unavailable',reason)
            self.started = self.last_frame = self.clock()
            self.active.update(state='running', started_utc=utc(), started_at=self.started,
                               reason='attention_admitted; developmental state retained')
            self._save(self.active)
            try:
                self.pipeline = self.factory(self.active['execution_id'])
                self.attention.object_display_error = None
                self.attention.object_labels.last_delivery = None
            except Exception as exc:self.finish('unavailable',type(exc).__name__+': '+str(exc)[:256])

    def tick(self):
        with self.lock:
            if self.active is None:return
            if self.cancel_requested:return self.finish('cancelled','operator_cancelled')
            if not self.running:
                if self.clock()-self.active['requested_at'] >= 30:self.finish('unavailable','attention_dispatch_timeout')
                return
            if self.attention.emergency_stopped:return self.finish('cancelled','emergency_stop')
            if self.clock()-self.started >= 15:
                if not self.active['observations']:return self.finish('failed','no_fresh_observations')
                reason = 'no_recognizable_objects' if not self.active['objects'] else (
                    'observations_and_display_acknowledgments; physical_output_unobserved' if self.active['display_acknowledgments']
                    else 'observations_without_stabilized_display_delivery')
                return self.finish('completed',reason)
            try:
                labels = self.attention.object_labels
                before = labels.stats['shown']
                result = self.pipeline.step()
                if result:
                    self.last_frame = self.clock()
                    self.active['observations'] += 1
                    self.active['objects'] += len(result['observation']['objects'])
                    self.active['display_acknowledgments'] += labels.stats['shown']-before
                    self.active['last_evidence_id'] = result['evidence_id']
                    self.active['last_objects'] = result['observation']['objects']
                    self._save(self.active, dict(result=result,
                        stabilization=dict(candidate=labels.candidate,hits=labels.hits,current=labels.current),
                        display=labels.last_delivery))
                error = getattr(self.attention,'object_display_error',None)
                delivery = labels.last_delivery
                if error or (delivery is not None and not delivery['acknowledged']):
                    return self.finish('failed',error or 'RP2040_display_not_acknowledged')
                if self.clock()-self.last_frame > 2:return self.finish('failed','camera_or_inference_stalled')
            except Exception as exc:self.finish('failed',type(exc).__name__+': '+str(exc)[:256])

    def finish(self, state, reason):
        with self.lock:
            if self.active is None:return
            row = self.active
            # End admission before cleanup; cleanup cannot resurrect activity.
            row.update(state=state, reason=reason, ended_utc=utc(),
                       elapsed_seconds=max(0,self.clock()-self.started) if self.started is not None else 0)
            try:
                self._save(row)
            except Exception as exc:
                self.record_error='evidence_persistence_failed:'+type(exc).__name__
                row.update(state='failed',reason=self.record_error)
            try:
                if self.pipeline is not None:
                    self.pipeline.close()
                    delivery=getattr(self.attention.object_labels,'last_delivery',None)
                    if isinstance(delivery,dict) and not delivery['acknowledged']:
                        raise OSError('RP2040 cleanup/display not acknowledged')
                    row['cleanup_display_receipt']=delivery if isinstance(delivery,dict) else None
            except Exception as exc:
                row.update(state='failed',reason='cleanup_failed:'+str(exc)[:256])
            finally:
                self.pipeline = None
                try:self._save(row)
                except Exception as exc:
                    self.record_error='evidence_persistence_failed:'+type(exc).__name__
                    row.update(state='failed',reason=self.record_error)
                self.terminal = dict(row)
                self.active = None
                self.started = None
                self.cancel_requested = False

    def close(self):
        self.finish('cancelled','application_shutdown')
        self.attention.demonstration = None
        self.db.close()
        os.close(self.owner_fd)


def recognition_factory(args, resources, frame_bus, attention, service_clock=time.monotonic):
    """Lazy existing pipeline, shared attention/display and application feeder only."""
    def create(execution_id):
        from learning.mobile import MobileEvidenceAdapter
        from learning.resources import ResourceGuard
        from memory.evidence import EvidenceJournal
        from stimulus.bus import StimulusBus
        from vision.mobile_models import HailoObjects, UnavailableDepth
        from vision.mobile_perception import MobilePerception, FrameArtifactStore, SelectiveFrameArtifacts
        from vision.object_recognition import ObjectRecognition
        import subprocess
        config=json.loads(args.object_model_manifest.read_text())
        if config.get('schema') != 'charlie.mobile.models.v1':raise ValueError('hash-bound model manifest required')
        owners=ExitStack()
        try:
            detector=HailoObjects(**dict(config['objects'],include_all=True))
            owners.callback(detector.close)
            revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[1],text=True).strip()
            journal=EvidenceJournal(args.learning_state/'mobile-evidence.sqlite3')
            owners.callback(journal.close)
            evidence=MobileEvidenceAdapter(journal,episode='operator-demo:'+execution_id,revision=revision)
            perception=MobilePerception(detector,UnavailableDepth(),resources=ResourceGuard(resources),revision=revision,clock=service_clock)
            pipeline=ObjectRecognition(frame_bus,perception,evidence,StimulusBus(),attention=attention)
            owners.callback(pipeline.close)
            pipeline.artifact_store=SelectiveFrameArtifacts(FrameArtifactStore(args.learning_state/'operator-demo-frames'))
            pipeline.select_camera('pi')
            pipeline.output_allowed=lambda: attention.demonstration.running and not attention.demonstration.cancel_requested and service_clock()-attention.demonstration.started<15
            class Lease:
                def step(self):return pipeline.step()
                def close(self):owners.close()
            return Lease()
        except BaseException:
            owners.close()
            raise
    return create
