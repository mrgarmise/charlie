"""Bounded reviewed-digit exemplar candidates for the existing HUD reader.

No camera, controller, scheduler or activation adapter. Training consultation is
explicit; loading an offline candidate never qualifies it or installs it live.
"""
from pathlib import Path
import hashlib
import json
import os
import numpy as np
import cv2
from memory.evidence import digest
from .robotron_hud import RobotronHUDReader,DigitRead
from .score_observer import ScoreObserver

SCHEMA='charlie-score-feedback-exemplars-v1'
MAX_EXEMPLARS=128


def feature(glyph):
    return (cv2.resize(glyph.astype(np.uint8),(16,24),interpolation=cv2.INTER_NEAREST)>0).astype(np.uint8).reshape(-1)


def reviewed_labels(journal, *, partition='training', allow_fixture=False):
    """Current unambiguous, independently attested reviews with verified originals.

    Diagnostic use must be requested explicitly. Final/validation labels cannot
    become development data. Returns exclusions instead of guessing labels.
    """
    if partition not in ('training','validation','final','diagnostic'):
        raise ValueError('explicit training, validation, final or diagnostic review partition required')
    proposals=journal.category_records('observation','score_review_proposal')
    if len(proposals)>4096:raise ValueError('bounded feedback requires <=4096 proposals')
    annotations=journal.category_records('observation','score_human_annotation')
    from .score_review_attestation import attested_photo_annotation_ids
    retrospectively_attested=attested_photo_annotation_ids(journal)
    superseded={r.data['payload'].get('supersedes') for r in annotations}
    statuses={r.data['payload'].get('proposal_id'):r.data['payload'].get('status') for r in
        journal.category_records('observation','score_review_status')}
    rows=[];excluded=[];seen=set()
    for record in proposals:
        p=record.data['payload'];key=record.id;sha=p['artifact']['sha256']
        if p['partition']!=partition:continue
        if sha in seen:continue
        aliases=[r for r in proposals if r.data['payload']['artifact']['sha256']==sha]
        peers=[r for r in annotations if r.id not in superseded and r.data['payload']['proposal_id'] in {a.id for a in aliases}]
        reason=None
        def same_source(q):
            return (q['artifact']['sha256']==sha or q['source_episode']==p['source_episode']
                or (q.get('context',{}).get('source_session') or q['source_episode'])==
                   (p.get('context',{}).get('source_session') or p['source_episode']))
        if any(a.data['payload']['partition']!=partition and same_source(a.data['payload']) for a in proposals):reason='source partition conflict'
        elif any(a.data['payload']['synthetic'] for a in aliases) and not allow_fixture:reason='fixture evidence excluded'
        elif any(statuses.get(a.id) in ('pending','insufficient','disputed') for a in aliases):reason='unresolved review status'
        elif not peers or any(r.data['payload'].get('independence_attested') is not True
                               and r.id not in retrospectively_attested for r in peers):
            reason='photo reading not attested (original submission or later linked confirmation required)'
        elif any(r.data['payload'].get('artifact_sha256')!=sha or r.data['payload'].get('source_episode')!=journal.get(r.data['payload']['proposal_id']).data['payload']['source_episode'] for r in peers):reason='annotation provenance mismatch'
        elif len({r.data['payload']['value'] for r in peers})!=1:reason='conflicting reviewer labels'
        elif next(iter({r.data['payload']['value'] for r in peers})) is None:reason='unreadable review'
        if not reason:
            try:path=ScoreObserver.review_artifact(journal,p)
            except (ValueError,OSError) as exc:reason=str(exc)
        if reason:excluded.append(dict(proposal_id=key,reason=reason));continue
        value=peers[0].data['payload']['value']
        if type(value) is not int or not 0<=value<=9999999:
            excluded.append(dict(proposal_id=key,reason='bounded nonnegative seven-digit label required'));continue
        rows.append(dict(proposal_id=key,proposal=p,label=value,path=path,annotation_ids=[r.id for r in peers]))
        seen.add(sha)
    return rows,excluded


def build_candidate(journal,calibration,output,*,partition='training',allow_fixture=False):
    """Existing journal and human-review protocol; exports an unqualified candidate."""
    from PIL import Image
    if Path(output).exists():raise FileExistsError('preserve existing candidate')
    labels,excluded=reviewed_labels(journal,partition=partition,allow_fixture=allow_fixture)
    reader=RobotronHUDReader(calibration);entries={};consulted=[];sources=[]
    for row in labels:
        p=row['proposal'];channel=p.get('context',{}).get('score_channel')
        # Historical queue sources explicitly contain P1 observations; no inference
        # from player identity, high-score lists or terminal screen is permitted.
        if channel is None:
            for source in journal.get(row['proposal_id']).data['sources']:
                payload=journal.get(source).data['payload']
                if payload.get('category')=='score_review_source' and isinstance(payload.get('score_row',{}).get('p1'),dict):channel=1
        if channel not in (1,2):
            excluded.append(dict(proposal_id=row['proposal_id'],reason='explicit score channel required'));continue
        recorded=p.get('context',{}).get('calibration_sha256')
        geometry=digest(dict(corners=calibration.corners,output_size=calibration.output_size))
        if recorded and p['context'].get('calibration_geometry_digest')!=geometry:
            excluded.append(dict(proposal_id=row['proposal_id'],reason='review calibration binding must match candidate geometry'));continue
        # Historical unlabeled calibration is a declared diagnostic limitation,
        # not a claim that guessed geometry is independently qualified.
        with Image.open(row['path']) as original:
            if original.width*original.height>16_000_000:raise ValueError('bounded source dimensions required')
            hud=np.asarray(reader.rectify(original.convert('RGB')))
        x=reader.P1_X if channel==1 else reader.P2_X
        pixels=hud[:,int(hud.shape[1]*x[0]):int(hud.shape[1]*x[1])]
        variants=[reader._glyphs_at_threshold(pixels,t) for t in (200,190,205)]
        if not all(variants):
            level=float(np.percentile(pixels.max(axis=2),99))
            thresholds=[max(60,min(160,int(level*f))) for f in (.4,.5,.6)]
            variants=([reader._glyphs_at_threshold(pixels,t) for t in thresholds]
                if level>=80 and len(set(thresholds))==3 else [])
        digits=str(row['label'])
        if not variants or any(len(glyphs)!=len(digits) for glyphs in variants):
            excluded.append(dict(proposal_id=row['proposal_id'],reason='segmentation does not independently establish labeled digit count'));continue
        additions=[]
        for glyph,digit in [(glyph,digit) for glyphs in variants for glyph,digit in zip(glyphs,digits)]:
            bits=''.join(map(str,feature(glyph).tolist()))
            additions.append((bits,digit))
        if len(set(entries)|{bits for bits,_ in additions})>MAX_EXEMPLARS:raise ValueError('bounded exemplar capacity exceeded')
        consulted.append(row['proposal_id']);sources.extend(row['annotation_ids'])
        for bits,digit in additions:entries.setdefault(bits,set()).add(digit)
    ambiguous=sum(len(v)>1 for v in entries.values())
    prototypes=[dict(bits=k,digit=next(iter(v))) for k,v in sorted(entries.items()) if len(v)==1]
    document=dict(schema=SCHEMA,geometry_digest=digest(dict(corners=calibration.corners,output_size=calibration.output_size)),
        reader_sha256=hashlib.sha256(Path(__file__).with_name('robotron_hud.py').read_bytes()).hexdigest(),
        prototypes=prototypes,training_proposal_ids=consulted,annotation_ids=sorted(set(sources)),
        excluded=excluded,ambiguous_features_excluded=ambiguous,partition=partition,
        fixture_only=bool(allow_fixture),qualification='unqualified offline candidate; no deployment or generalization inferred',
        physical_authorization=False,confidence_cap=.9)
    document['state_digest']=digest(document)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    # A completed artifact is immutable; interruption leaves a new temp, not a
    # usable partial model. Never overwrite an earlier candidate.
    temporary=output.with_name(output.name+'.pending')
    with temporary.open('x') as stream:
        stream.write(json.dumps(document,sort_keys=True,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
    try:os.link(temporary,output)
    finally:temporary.unlink(missing_ok=True)
    references=[]
    for identifier in sorted(set(consulted+sources)):
        original=journal.get(identifier)
        references.append(journal.append('observation',dict(category='consolidated_evidence_reference',
            record_id=identifier,source_episode=original.data['episode'],journal=str(journal.path.resolve())),
            episode='score-reader-exemplar-development',producer='existing-evidence-consolidation',version=SCHEMA).id)
    record=journal.append('observation',dict(category='score_reader_candidate',
        training_proposal_ids=consulted,reader_revision=document['state_digest'],artifact=str(output.resolve()),
        artifact_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),state_digest=document['state_digest'],
        fixture_only=bool(allow_fixture),physical_authorization=False,qualification=document['qualification']),
        episode='score-reader-exemplar-development',sources=references,
        producer='ModelFoundry',version=SCHEMA)
    return record,document


class ScoreFeedbackReader(RobotronHUDReader):
    @classmethod
    def load(cls,path,calibration,*,allow_fixture=False,expected_state_digest=None,expected_artifact_sha256=None):
        path=Path(path)
        if path.stat().st_size>1_000_000:raise ValueError('bounded feedback artifact required')
        raw=path.read_bytes()
        if expected_artifact_sha256 and hashlib.sha256(raw).hexdigest()!=expected_artifact_sha256:raise ValueError('feedback candidate artifact mismatch')
        d=json.loads(raw);expected=digest({k:v for k,v in d.items() if k!='state_digest'})
        if d.get('schema')!=SCHEMA or d.get('state_digest')!=expected:raise ValueError('feedback integrity mismatch')
        if expected_state_digest and d['state_digest']!=expected_state_digest:raise ValueError('feedback candidate identity mismatch')
        if d['geometry_digest']!=digest(dict(corners=calibration.corners,output_size=calibration.output_size)):
            raise ValueError('feedback calibration mismatch')
        if d['reader_sha256']!=hashlib.sha256(Path(__file__).with_name('robotron_hud.py').read_bytes()).hexdigest():
            raise ValueError('feedback extraction revision mismatch')
        if d.get('fixture_only') and not allow_fixture:raise ValueError('fixture feedback requires explicit offline test admission')
        rows=d['prototypes']
        if len(rows)>MAX_EXEMPLARS or any(r['digit'] not in '0123456789' or len(r['digit'])!=1 or len(r['bits'])!=384 or set(r['bits'])-{'0','1'} for r in rows):raise ValueError('invalid feedback prototypes')
        if d.get('physical_authorization') is not False or d.get('confidence_cap')!=.9:raise ValueError('invalid feedback authority/confidence')
        values=np.array([[int(v) for v in r['bits']] for r in rows],dtype=np.uint8)
        base=RobotronHUDReader
        class Adapted(cls):
            @classmethod
            def _read_digit(klass,glyph):
                if not rows:return base._read_digit(glyph)
                distances=np.mean(values!=feature(glyph),axis=1)
                best={}
                for row,dist in zip(rows,distances):best[row['digit']]=min(best.get(row['digit'],1.),float(dist))
                ranked=sorted((v,k) for k,v in best.items());distance,digit=ranked[0]
                # Very narrow exemplar neighborhood and an explicit alternative
                # margin. Ambiguous/nearly matching shapes abstain from adaptation.
                if distance<=.02 and (len(ranked)==1 or ranked[1][0]-distance>.02):
                    return DigitRead(digit,min(.9,.9-distance),0)
                return base._read_digit(glyph)
        reader=Adapted(calibration);reader.feedback_state_digest=d['state_digest'];reader.feedback_document=d
        return reader
