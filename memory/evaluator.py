"""Revisable memory selection and usefulness evidence.

Episodes are observations. Usefulness feedback needs an explicit comparison or
human correction; temporal proximity alone never counts as proof of benefit.
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from contextlib import contextmanager
import sqlite3
from typing import Literal

from .former import CandidateMemory, Experience, MemoryFormer
from .marm import DEFAULT_OUTBOX

DEFAULT_EVALUATIONS = DEFAULT_OUTBOX.with_name("memory-evaluation.sqlite3")


@dataclass(frozen=True)
class Evaluation:
    id: str
    candidate: CandidateMemory
    priority: float
    promote: bool
    reason: str


class MemoryEvaluator:
    """Keeps provisional evidence, category statistics, decisions and corrections."""

    THRESHOLD = 0.4

    @staticmethod
    def reconcile_score_reviews(journal):
        """Expose immutable reviewer outcomes as diagnostic evidence, not an agenda."""
        from experiments.ppal.score_observer import ScoreObserver
        annotations=journal.category_records('observation','score_human_annotation')
        statuses=journal.category_records('observation','score_review_status')
        if not annotations and not statuses:return None
        return journal.append('observation',dict(category='score_reader_review_reconciliation',
            annotation_ids=[r.id for r in annotations],status_ids=[r.id for r in statuses],
            metrics={p:ScoreObserver.review_metrics(journal,partition=p) for p in ('diagnostic','training','validation','final')},
            interpretation='reviewer observations; no physical score qualification or selected learning priority',
            physical_authorization=False),episode='score-review-diagnostics',
            producer='MemoryEvaluator',version='score-feedback-v1')

    @staticmethod
    def evaluate_score_reader(journal,candidate_id,reader,*,partition='validation',allow_fixture=False):
        try:
            return MemoryEvaluator._evaluate_score_reader(journal,candidate_id,reader,
                partition=partition,allow_fixture=allow_fixture)
        except (ValueError,KeyError,OSError,TypeError,RuntimeError) as exc:
            journal.append('observation',dict(category='score_reader_candidate_evaluation',
                candidate_id=candidate_id,report=dict(status='rejected',partition=partition,reason=str(exc),
                    fixture_only=bool(allow_fixture),physical_authorization=False,
                    qualification='failed offline evaluation preserved; no improvement or deployment inferred')),
                episode='score-reader-rejected-evaluation',producer='MemoryEvaluator',version='score-feedback-v1')
            raise

    @staticmethod
    def _evaluate_score_reader(journal,candidate_id,reader,*,partition='validation',allow_fixture=False):
        """Bounded independent offline comparison against immutable pre-review predictions.

        Caller supplies an existing Charlie-originated candidate. No candidate is
        generated, selected, activated or promoted here. Final evidence requires
        an independent sealed protocol and is deliberately unavailable here.
        """
        import math,time
        from PIL import Image
        candidate=journal.get(candidate_id);payload=candidate.data['payload']
        if candidate.data['producer'] not in ('Reflection','ModelFoundry'):
            raise ValueError('existing Charlie-originated candidate required')
        if partition not in ('validation','diagnostic'):raise ValueError('sealed final evaluation requires independent protocol')
        training=payload.get('training_proposal_ids')
        if not isinstance(training,list):raise ValueError('explicit candidate training consultation required')
        proposals={r.id:r.data['payload'] for r in journal.category_records('observation','score_review_proposal')}
        used=[proposals[i] for i in training]
        def identity(p):
            return {('image',p['artifact']['sha256']),('episode',p['source_episode']),
                ('session',p.get('context',{}).get('source_session') or p['source_episode'])}
        consulted=set().union(*(identity(p) for p in used)) if used else set()
        annotations=journal.category_records('observation','score_human_annotation')
        superseded={r.data['payload'].get('supersedes') for r in annotations}
        status={r.data['payload'].get('proposal_id'):r.data['payload']['status'] for r in journal.category_records('observation','score_review_status')}
        samples=[];seen=set();deficiencies=[]
        if len(proposals)>4096:raise ValueError('bounded review evaluation requires a smaller journal snapshot')
        for key,p in proposals.items():
            if p['partition']!=partition or p['synthetic'] and not allow_fixture:continue
            if identity(p)&consulted:raise ValueError('candidate training overlaps evaluation game, session or image')
            if p['artifact']['sha256'] in seen:continue
            if status.get(key) in ('pending','insufficient','disputed'):continue
            aliases={k for k,q in proposals.items() if q['artifact']['sha256']==p['artifact']['sha256']}
            if len({(proposals[k]['proposed_score'],proposals[k]['confidence']) for k in aliases})!=1:continue
            peers=[r for r in annotations if r.id not in superseded and r.data['payload']['proposal_id'] in aliases
                and r.data['payload']['independence_attested']]
            values={r.data['payload']['value'] for r in peers}
            if len(values)!=1 or None in values:continue
            revision=p.get('context',{}).get('reader_revision')
            if not revision:deficiencies.append('frozen original reader revision missing');continue
            from experiments.ppal.score_observer import ScoreObserver
            ScoreObserver.review_artifact(journal,p)
            # All merged diaries must obey the same partition boundary.
            if any(q['partition']!=partition and identity(q)&identity(p) for q in proposals.values()):
                raise ValueError('source crosses evaluation partitions')
            seen.add(p['artifact']['sha256'])
            samples.append((key,p,values.pop(),[r.id for r in peers]))
        if len(samples)>256:raise ValueError('bounded candidate evaluation permits at most 256 originals')
        revisions={p['context']['reader_revision'] for _,p,_,_ in samples}
        if len(revisions)>1:raise ValueError('mixed reader baselines forbidden')
        frozen=journal.append('observation',dict(category='score_reader_frozen_baseline',
            reader_revision=next(iter(revisions),None),partition=partition,
            predictions=[dict(proposal_id=k,value=p['proposed_score'],confidence=p['confidence']) for k,p,_,_ in samples]),
            episode=candidate.data['episode'],producer='MemoryEvaluator',version='score-feedback-v1')
        outcomes=[]
        for key,p,label,labels in samples:
            begin=time.monotonic()
            with Image.open(ScoreObserver.review_artifact(journal,p)) as original:answer=reader(original.copy())
            seconds=time.monotonic()-begin
            if not isinstance(answer,(tuple,list)) or len(answer)!=2:raise ValueError('candidate must return score and confidence')
            value,confidence=answer
            if value is not None and (type(value) is not int or value<0):raise ValueError('invalid candidate score')
            if type(confidence) not in (float,int) or not math.isfinite(confidence) or not 0<=confidence<=1:
                raise ValueError('invalid candidate confidence')
            outcomes.append(dict(proposal_id=key,label=label,annotation_ids=labels,baseline=p['proposed_score'],
                candidate=value,confidence=confidence,seconds=seconds))
        n=len(outcomes)
        def metrics(field):
            accepted=[r for r in outcomes if r[field] is not None]
            return dict(samples=n,accepted=len(accepted),abstained=n-len(accepted),
                exact_accuracy=sum(r[field]==r['label'] for r in accepted)/len(accepted) if accepted else None)
        report=dict(status='measured_offline_batch' if n else 'unresolved',partition=partition,
            baseline=metrics('baseline'),candidate=metrics('candidate'),
            false_high_confidence=sum(r['candidate'] is not None and r['candidate']!=r['label'] and r['confidence']>=.99 for r in outcomes),
            total_seconds=sum(r['seconds'] for r in outcomes),outcomes=outcomes,deficiencies=deficiencies,
            missing_requirements=['Independent readable original reviews in the requested partition, a frozen reader revision, and training-disjoint source groups'] if not n else [],
            fixture_only=bool(allow_fixture),qualification='descriptive reviewed batch; no sealed final, physical capability or deployment authority',
            uncertainty='finite labeled sample; correlated frames do not establish population improvement',physical_authorization=False)
        return journal.append('observation',dict(category='score_reader_candidate_evaluation',candidate_id=candidate_id,
            baseline_id=frozen.id,training_consultation=training,report=report),episode=candidate.data['episode'],
            sources=[candidate_id,frozen.id],producer='MemoryEvaluator',version='score-feedback-v1')


    def __init__(self, path=DEFAULT_EVALUATIONS, exploration_rate=0.05):
        if not 0 <= exploration_rate <= 1:
            raise ValueError("exploration_rate must be within [0, 1]")
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.exploration_rate = exploration_rate
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY, feature TEXT NOT NULL, payload TEXT NOT NULL,
                    status TEXT NOT NULL, priority REAL NOT NULL, reason TEXT NOT NULL,
                    remote_key TEXT
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY, memory_id TEXT NOT NULL, verdict TEXT NOT NULL,
                    weight REAL NOT NULL, rationale TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT NOT NULL, memory_id TEXT NOT NULL, task TEXT NOT NULL,
                    PRIMARY KEY(decision_id, memory_id)
                );
                CREATE TABLE IF NOT EXISTS corrections (
                    memory_id TEXT PRIMARY KEY, replacement TEXT NOT NULL, rationale TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_candidates_remote ON candidates(remote_key);
            """)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def feature(event: Experience) -> str:
        # Exact tags preserve task distinctions; broad categories share examples.
        return json.dumps([event.source, event.kind, sorted(event.tags)], separators=(",", ":"))

    @staticmethod
    def identity(candidate: CandidateMemory) -> str:
        # An evidence ID represents one episode even if its description changes.
        # Without one, identical claims are one candidate across restarts.
        key = [candidate.source, candidate.kind,
               candidate.evidence if candidate.evidence else candidate.text]
        return hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()

    def _posterior(self, conn, feature):
        row = conn.execute("""SELECT
            COALESCE(SUM(CASE WHEN verdict='helpful' THEN weight ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN verdict='harmful' THEN weight ELSE 0 END),0),
            COUNT(*) FROM evidence JOIN candidates ON candidates.id=evidence.memory_id
            WHERE candidates.feature=? AND verdict IN ('helpful','harmful')""", (feature,)).fetchone()
        good, bad, count = row
        return (1 + good) / (2 + good + bad), count

    def _score(self, conn, candidate, feature, identifier):
        usefulness, samples = self._posterior(conn, feature)
        score = candidate.importance * (0.65 + 0.7 * (usefulness - 0.5))
        if samples >= 3:
            score = max(score, usefulness * 0.75)
        explore = int(identifier[:8], 16) / 0xFFFFFFFF < self.exploration_rate
        return min(1.0, max(0.0, score)), explore

    def consider(self, event: Experience) -> Evaluation | None:
        candidate = MemoryFormer(threshold=0).consider(event)
        if candidate is None:
            return None
        identifier = self.identity(candidate)
        feature = self.feature(event)
        with self._connect() as conn:
            existing = conn.execute("SELECT status, priority, reason, payload FROM candidates WHERE id=?",
                                    (identifier,)).fetchone()
            if existing:
                return Evaluation(identifier, CandidateMemory(**json.loads(existing[3])),
                                  existing[1], existing[0] == "provisional" and existing[1] >= self.THRESHOLD,
                                  existing[2])
            score, explore = self._score(conn, candidate, feature, identifier)
            promote = score >= self.THRESHOLD or explore
            reason = "usefulness and significance" if score >= self.THRESHOLD else (
                "exploration sample" if explore else "provisional")
            conn.execute("INSERT INTO candidates(id,feature,payload,status,priority,reason) VALUES (?,?,?,?,?,?)",
                         (identifier, feature, json.dumps(candidate.to_dict()),
                          "provisional", score, reason))
        return Evaluation(identifier, candidate, score, promote, reason)

    def link_remote(self, identifier, remote_key):
        with self._connect() as conn:
            conn.execute("UPDATE candidates SET remote_key=? WHERE id=?", (remote_key, identifier))

    def resolve_remote(self, remote_key):
        with self._connect() as conn:
            row = conn.execute("SELECT id, status FROM candidates WHERE remote_key=?", (remote_key,)).fetchone()
        return row  # None means older/unmanaged MARM memory.

    def mark_promoted(self, identifier):
        with self._connect() as conn:
            conn.execute("UPDATE candidates SET status='promoted' WHERE id=? AND status='provisional'", (identifier,))

    def feedback(self, identifier: str, verdict: Literal["helpful", "harmful"],
                 evidence_id: str, rationale: str, weight: float = 1.0) -> bool:
        """Explicit, deduplicated assessment; never infer from action timing."""
        if verdict not in ("helpful", "harmful") or not evidence_id.strip() or not rationale.strip():
            raise ValueError("Feedback needs a verdict, unique evidence ID and rationale")
        if not 0 < weight <= 2:
            raise ValueError("Feedback weight must be within (0, 2]")
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM candidates WHERE id=?", (identifier,)).fetchone() is None:
                raise KeyError(identifier)
            result = conn.execute("INSERT OR IGNORE INTO evidence VALUES (?,?,?,?,?)",
                                  (evidence_id, identifier, verdict, weight, rationale))
            inserted = result.rowcount == 1
        if inserted:
            self.refresh()
        return inserted

    def refresh(self):
        """Re-rate active claims as contrary evidence arrives or is revised."""
        with self._connect() as conn:
            rows = conn.execute("SELECT id, feature, payload, status FROM candidates WHERE status!='superseded'").fetchall()
            for identifier, feature, payload, status in rows:
                candidate = CandidateMemory(**json.loads(payload))
                priority, _ = self._score(conn, candidate, feature, identifier)
                if status in ('promoted', 'dormant'):
                    new_status = 'promoted' if priority >= self.THRESHOLD else 'dormant'
                else:
                    new_status = 'provisional'
                conn.execute("UPDATE candidates SET priority=?, status=? WHERE id=?",
                             (priority, new_status, identifier))

    def record_decision(self, decision_id: str, task: str, memory_ids: list[str]):
        """Track actual use, not merely recall. No usefulness credit yet."""
        if not decision_id.strip() or not task.strip():
            raise ValueError("Decision and task IDs are required")
        with self._connect() as conn:
            for identifier in set(memory_ids):
                if conn.execute("SELECT 1 FROM candidates WHERE id=? AND status='promoted'", (identifier,)).fetchone() is None:
                    raise KeyError(identifier)
                conn.execute("INSERT OR IGNORE INTO decisions VALUES (?,?,?)",
                             (decision_id, identifier, task))

    def assess_decision(self, decision_id: str, verdict: Literal["helpful", "harmful"],
                        evidence_id: str, comparison: str, weight: float = 1.0) -> int:
        """Credit an outcome only when a comparison/rationale is supplied."""
        if not comparison.strip():
            raise ValueError("Explain the comparison behind this assessment")
        with self._connect() as conn:
            ids = [row[0] for row in conn.execute("SELECT memory_id FROM decisions WHERE decision_id=?",
                                                   (decision_id,))]
        if not ids:
            raise KeyError(decision_id)
        # Split credit among influences; never count one outcome N times.
        return sum(self.feedback(identifier, verdict, evidence_id + ":" + identifier,
                                 comparison, weight / len(ids)) for identifier in ids)

    def correct(self, identifier: str, replacement: str, rationale: str):
        """Supersede a false or stale memory without erasing its history."""
        if not replacement.strip() or not rationale.strip():
            raise ValueError("Correction and rationale are required")
        with self._connect() as conn:
            row = conn.execute("SELECT feature FROM candidates WHERE id=?", (identifier,)).fetchone()
            if row is None:
                raise KeyError(identifier)
            conn.execute("INSERT INTO corrections VALUES (?,?,?) ON CONFLICT(memory_id) DO UPDATE SET replacement=excluded.replacement, rationale=excluded.rationale",
                         (identifier, replacement, rationale))
            conn.execute("UPDATE candidates SET status='superseded' WHERE id=?", (identifier,))
        # Correction is scoped to this claim; it does not condemn every memory
        # from the same producer/category. Other claims need their own evidence.

    def is_active(self, identifier: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT status FROM candidates WHERE id=?", (identifier,)).fetchone()
        return row is None or row[0] == "promoted"

    def review_pending(self, limit=100) -> list[Evaluation]:
        """Reconsider provisional candidates after feedback changes a category."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be within 1..1000")
        selections = []
        with self._connect() as conn:
            rows = conn.execute("SELECT id, feature, payload FROM candidates WHERE status='provisional' ORDER BY rowid LIMIT ?", (limit,)).fetchall()
            for identifier, feature, payload in rows:
                candidate = CandidateMemory(**json.loads(payload))
                score, _ = self._score(conn, candidate, feature, identifier)
                if score >= self.THRESHOLD:
                    conn.execute("UPDATE candidates SET priority=?, reason=? WHERE id=?",
                                 (score, "reconsidered with new evidence", identifier))
                    selections.append(Evaluation(identifier, candidate, score, True,
                                                 "reconsidered with new evidence"))
        return selections

    def recent(self, limit=20):
        if not 1 <= limit <= 100:
            raise ValueError("limit must be within 1..100")
        with self._connect() as conn:
            rows = conn.execute("SELECT id,status,priority,payload FROM candidates ORDER BY rowid DESC LIMIT ?",
                                (limit,)).fetchall()
        return [{"id": identifier, "status": status, "priority": priority,
                 **{k:json.loads(payload).get(k) for k in ('text','source','tags','confidence','evidence')}}
                for identifier, status, priority, payload in rows]

    def for_evidence(self, evidence_ids):
        """Retrieve a persistent project's hypotheses beyond the recent window."""
        ids = list(dict.fromkeys(evidence_ids)); rows = []
        with self._connect() as conn:
            for offset in range(0, len(ids), 100):
                batch = ids[offset:offset+100]
                marks = ','.join('?' for _ in batch)
                rows.extend(conn.execute(
                    f"SELECT id,status,priority,payload FROM candidates WHERE json_extract(payload,'$.evidence') IN ({marks}) ORDER BY rowid DESC",
                    batch).fetchall())
        return [{"id": identifier, "status": status, "priority": priority,
                 **{k:json.loads(payload).get(k) for k in ('text','source','tags','confidence','evidence')}}
                for identifier, status, priority, payload in rows]

    @staticmethod
    def reconcile_perception(journal, capture_root):
        """Offline exact-source reconciliation; no camera, frame substitution or learning agenda.

        Independently supplied visual measurements must bind exact original
        pixels/clock/geometry and declare uncertainty. Detector output is one
        witness, never the independent measurement of itself.
        """
        import math
        from .evidence import digest
        root=Path(capture_root).resolve()
        cameras={r.id:r for r in journal.category_records('observation','camera_observation')}
        captures={r.data['payload']['observation_id']:r for r in journal.category_records('observation','camera_capture')}
        independent={}
        for r in journal.category_records('observation','independent_visual_measurement'):
            independent.setdefault(r.data['payload'].get('observation_id'),[]).append(r)
        outputs=[]
        for trace in journal.category_records('observation','detector_trace'):
            p=trace.data['payload'];identifier=p.get('observation_id');source=cameras.get(identifier)
            if source is None:continue
            capture=captures.get(identifier);judgments=[];references=[trace.id,source.id]
            original=None
            if capture:
                artifact=capture.data['payload']['artifact'];path=root/artifact['path']
                if path.is_symlink() or root not in path.resolve().parents or hashlib.sha256(path.read_bytes()).hexdigest()!=artifact['sha256']:
                    raise ValueError('independent source pixels missing or changed')
                original=artifact;references.append(capture.id)
            measurements=independent.get(identifier,[])
            valid=[]
            for witness in measurements:
                q=witness.data['payload']
                try:
                    method=journal.get(q.get('method_reference'));m=method.data['payload'];proof=m.get('qualification_artifact',{})
                    qualified=(method.data['producer']=='independent-visual-measurement' and m.get('category')=='visual_measurement_method_qualification'
                        and m.get('status')=='verified' and proof.get('path') and
                        hashlib.sha256(Path(proof['path']).read_bytes()).hexdigest()==proof.get('sha256'))
                except (KeyError,TypeError,OSError):qualified=False
                if (qualified and witness.data['producer']=='independent-visual-measurement' and original
                    and q.get('artifact_sha256')==original['sha256'] and q.get('timestamp')==source.data['at']
                    and q.get('geometry_sha256')==digest(p.get('geometry'))
                    and q.get('method_reference') and q.get('identity_association')=='independently_qualified'):
                    valid.append(witness);references.extend([method.id,witness.id])
            for index,detection in enumerate(p.get('detections',[])):
                point=detection.get('center',[])
                sane=len(point)==2 and all(isinstance(v,(float,int)) and math.isfinite(v) and 0<=v<=100 for v in point)
                matching=[w for w in valid if w.data['payload'].get('detection_index')==index]
                verdict='plausible_but_not_independently_observed' if sane and not original else 'unresolved'
                reason='internal normalized measurement only; originals not retained' if verdict.startswith('plausible') else 'original pixels do not independently certify detection; qualified visual measurement missing'
                errors=[]
                for witness in matching:
                    q=witness.data['payload'];other=q.get('center',[]);bound=q.get('position_uncertainty');internal=q.get('internal_position_uncertainty')
                    if (not sane or len(other)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in other)
                        or not all(isinstance(v,(int,float)) and math.isfinite(v) and v>=0 for v in (bound,internal))):continue
                    error=math.hypot(point[0]-other[0],point[1]-other[1]);errors.append(dict(distance=error,bound=bound+internal,measurement_id=witness.id))
                if errors:
                    outcomes={e['distance']<=e['bound'] for e in errors}
                    verdict='corroborated' if outcomes=={True} else 'disputed' if outcomes=={False} else 'unresolved'
                    reason='exact original source and declared independent uncertainty; disagreement retained'
                judgments.append(dict(detection_index=index,status=verdict,reason=reason,calculations=errors,
                    alternatives=['identity association uncertainty','timing/occlusion/motion uncertainty','detector error'],
                    causation='unqualified; no nearest-frame or interpolated truth'))
            finding=journal.append('observation',dict(category='perception_reconciliation',schema='visual-reconciliation-v1',
                observation_id=identifier,trace_id=trace.id,source_timestamp=source.data['at'],original=original,
                judgments=judgments,independent_measurements=[r.id for r in valid],
                source_capture=str(root),new_independent_experience=False),episode=trace.data['episode'],
                sources=list(dict.fromkeys(references)),producer='independent-evidence-reconciler',version='1')
            outputs.append(finding)
        return outputs

    def stats(self, source: str, kind: str, tags=()):
        feature = json.dumps([source, kind, sorted(tags)], separators=(",", ":"))
        with self._connect() as conn:
            posterior, count = self._posterior(conn, feature)
        return {"estimated_usefulness": posterior, "evidence_count": count}
