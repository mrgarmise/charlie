"""Inspect Robotron score reading on saved raw camera frames."""
from __future__ import annotations

import argparse
import json
import hashlib
import html
import base64
from pathlib import Path

from PIL import Image

from .eyes.calibration import Calibration
from .robotron_hud import RobotronHUDReader
from .score_tracker import VisualScoreTracker


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("frames", nargs="*", type=Path)
    ap.add_argument("--calibration", type=Path,
                    default=Path("config/robotron/playfield-latest.json"))
    ap.add_argument("--output", type=Path)
    ap.add_argument("--self-channel", type=int, choices=(1,2), default=1)
    ap.add_argument('--review-journal',type=Path)
    ap.add_argument('--source-episode')
    ap.add_argument('--source-record',help='exact original observation ID already imported into review journal')
    ap.add_argument('--source-session')
    ap.add_argument('--timestamp',type=float,help='original acquisition timestamp; required for new proposal')
    ap.add_argument('--clock',default='monotonic')
    ap.add_argument('--partition',choices=['training','validation','final','diagnostic'],default='diagnostic')
    ap.add_argument('--synthetic',action='store_true')
    ap.add_argument('--review-proposal')
    ap.add_argument('--annotator')
    ap.add_argument('--verdict',choices=['confirm','correct','unreadable'])
    ap.add_argument('--correct-score',type=int)
    ap.add_argument('--reason')
    ap.add_argument('--independent-review',action='store_true',help='reviewer attests independent annotation; does not qualify a game')
    ap.add_argument('--review-metrics',action='store_true')
    ap.add_argument('--queue-root',type=Path,help='authorized saved marathon/game tree')
    ap.add_argument('--serve-review',action='store_true',help='deferred review on loopback; no gameplay capability')
    ap.add_argument('--review-port',type=int,default=8769)
    ap.add_argument('--freeze-baseline',help='immutable baseline name from qualified complete games')
    ap.add_argument('--baseline-policy',help='exact qualified policy identity')
    ap.add_argument('--baseline-count',type=int,default=10)
    args=ap.parse_args()
    from .score_observer import ScoreObserver
    if args.freeze_baseline:
        if not args.review_journal or not args.review_journal.is_file() or not args.baseline_policy:ap.error('existing journal and exact baseline policy required')
        from memory.evidence import EvidenceJournal
        j=EvidenceJournal(args.review_journal)
        try:
            rows=performance_history(j).get(args.baseline_policy,{}).get('records',[])
            if args.baseline_count<1 or len(rows)<args.baseline_count:raise ValueError('insufficient qualified complete games')
            result=freeze_baseline(j,args.freeze_baseline,args.baseline_policy,[r['id'] for r in rows[-args.baseline_count:]])
            print(json.dumps(result.data,indent=2))
        finally:j.close()
        return
    if args.queue_root or args.serve_review:
        if not args.review_journal or not args.review_journal.is_file():ap.error('existing operator review journal required')
        if args.serve_review:
            serve_review(args.review_journal,args.queue_root,args.review_port)
        else:
            from memory.evidence import EvidenceJournal
            j=EvidenceJournal(args.review_journal)
            try:
                import_queue(j,args.queue_root)
                print(json.dumps(queue_rows(j),indent=2))
            finally:j.close()
        return
    if args.review_proposal or args.review_metrics:
        if not args.review_journal:ap.error('review journal required')
        from memory.evidence import EvidenceJournal
        j=EvidenceJournal(args.review_journal)
        try:
            if args.review_metrics:
                result=ScoreObserver.review_metrics(j,partition=args.partition)
            else:
                if not args.annotator or not args.verdict or not args.reason:ap.error('annotator, verdict and reason required')
                result=ScoreObserver.annotate_review(j,args.review_proposal,annotator=args.annotator,
                    verdict=args.verdict,value=args.correct_score,reason=args.reason,independent=args.independent_review).data
            print(json.dumps(result,indent=2))
        finally:j.close()
        return
    if not args.frames:ap.error('original saved frames required')
    if args.review_journal and (len(args.frames)!=1 or not args.source_episode or args.timestamp is None):
        ap.error('new review proposal requires one original frame, source episode and exact timestamp')

    cal=Calibration.load(args.calibration)
    reader=RobotronHUDReader(cal)
    tracker=VisualScoreTracker(reader, self_channel=args.self_channel)
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)

    for index,path in enumerate(args.frames):
        image=Image.open(path).convert("RGB")
        hud=reader.rectify(image)
        if args.output:
            hud.save(args.output/f"hud-{index:03d}.png")
        scores=tracker.observe(image)
        row={
            "frame":str(path),
            "p1":{"score":scores.player1.score,
                  "observed":scores.player1.observed_score,
                  "confidence":round(scores.player1.confidence,4),
                  "status":scores.player1.status},
            "p2":{"score":scores.player2.score,
                  "observed":scores.player2.observed_score,
                  "confidence":round(scores.player2.confidence,4),
                  "status":scores.player2.status},
            "self_score":scores.self_score,
        }
        if args.review_journal:
            from memory.evidence import EvidenceJournal
            j=EvidenceJournal(args.review_journal)
            try:
                proposal=ScoreObserver.review_proposal(j,path,source_episode=args.source_episode,
                    timestamp=args.timestamp,clock=args.clock,source_id=args.source_record,
                    proposed=scores.player1.observed_score if args.self_channel==1 else scores.player2.observed_score,
                    confidence=scores.player1.confidence if args.self_channel==1 else scores.player2.confidence,
                    partition=args.partition,synthetic=args.synthetic,
                    context=dict(source_session=args.source_session,calibration_sha256=hashlib.sha256(args.calibration.read_bytes()).hexdigest(),
                        reader_revision=hashlib.sha256(Path(__file__).with_name('robotron_hud.py').read_bytes()).hexdigest()))
                row['review_proposal_id']=proposal.id
                if args.output:
                    # Existing inspection output gains a local original/crop review; no server or camera.
                    encoded=base64.b64encode(path.read_bytes()).decode()
                    mime='image/png' if path.suffix.lower()=='.png' else 'image/jpeg'
                    page='<meta charset="utf-8"><title>Original Robotron score review</title><h1>Unqualified score proposal</h1>'
                    page+='<pre>'+html.escape(json.dumps(row,indent=2))+'</pre>'
                    page+='<h2>Original source</h2><img style="max-width:100%" src="data:'+mime+';base64,'+encoded+'">'
                    page+='<h2>Rectified HUD (derived)</h2><img src="hud-'+f'{index:03d}'+'.png">'
                    page+='<p>Confirm, correct or mark unreadable using --review-proposal '+proposal.id+'. Original proposal is immutable. No complete-game score qualification.</p>'
                    (args.output/'score-review.html').write_text(page)
            finally:j.close()
        print(json.dumps(row,sort_keys=True))


def import_queue(journal, root):
    """Read existing diaries and immutable originals; aliases are not new games."""
    from memory.evidence import EvidenceJournal
    from .score_observer import ScoreObserver
    root=Path(root).resolve()
    if not root.is_dir():raise ValueError('authorized saved evidence root unavailable')
    def deficiency(path,exc):
        from memory.evidence import digest
        try:content=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except OSError:content=None
        journal.append('observation',dict(category='score_acquisition_deficiency',source_path=str(path),
            source_sha256=content,reason=str(exc),physical_authorization=False),
            episode='score-review-acquisition',producer='existing-acquisition-capability',version='score-feedback-v1')
    # Existing session diary includes attempts without report.json.
    for path in sorted(set(root.rglob('experiment-evidence.sqlite3')) | set(root.rglob('session-evidence.sqlite3'))):
        if path.resolve()==journal.path.resolve():continue
        import sqlite3
        try:
            source=EvidenceJournal(path,read_only=True)
            try:journal.merge_from(source)
            finally:source.close()
        except (OSError,ValueError,KeyError,sqlite3.DatabaseError) as exc:deficiency(path,exc)
    for path in sorted(root.rglob('report.json')):
        folder=path.parent
        try:
            parent=json.loads((folder.parent/'session.json').read_text())
            number=next((i+1 for i,g in enumerate(parent.get('games',[])) if Path(g['path']).name==folder.name),None)
        except (OSError,ValueError,KeyError,TypeError,AttributeError):number=None
        try:ScoreObserver.queue_game(journal,folder,session=folder.parent,number=number or folder.name)
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:deficiency(path,exc)


def queue_rows(journal):
    """Project immutable history; changing a review never rewrites a prediction."""
    games={}
    for r in journal.category_records('observation','score_game_record'):
        p=r.data['payload'];games[p['attempt_id']]=dict(p,id=r.id)
    unique={}
    for p in games.values():
        key=p['capture_key']
        if key not in unique or (p['report_sha256'] and not unique[key]['report_sha256']):unique[key]=p
    annotations=journal.category_records('observation','score_human_annotation')
    superseded={r.data['payload'].get('supersedes') for r in annotations}
    statuses={r.data['payload']['attempt_id']:r.data['payload'] for r in journal.category_records('observation','score_review_status')}
    result=[]
    for p in unique.values():
        proposal=journal.get(p['proposal_id']).data['payload'] if p['proposal_id'] else None
        peers=[r for r in annotations if r.id not in superseded and r.data['payload']['proposal_id']==p['proposal_id']]
        previous=statuses.get(p['attempt_id'],{})
        status=previous.get('status','pending') if previous.get('proposal_id')==p['proposal_id'] else 'pending'
        if len({r.data['payload']['value'] for r in peers})>1:status='disputed'
        if proposal:
            p.update(proposed_score=proposal['proposed_score'],confidence=proposal['confidence'],
                timestamp=proposal['timestamp'],terminal_support=proposal['context'].get('terminal_support',False))
        else:p.update(proposed_score=None,confidence=None,timestamp=None,terminal_support=False)
        p.update(review_status=status,review=statuses.get(p['attempt_id']),
            annotation_history=[dict(id=r.id,**r.data['payload']) for r in annotations if r.data['payload']['proposal_id']==p['proposal_id']],
            annotations=[dict(id=r.id,**r.data['payload']) for r in peers])
        result.append(p)
    return sorted(result,key=lambda p:(p['session'],str(p['number']).zfill(5)))


def review_game(journal, identifier, *, annotator, verdict, value=None, reason='', independent=False):
    if (journal.path.parent/'capture-manifest.json').is_file():
        raise ValueError('review must use consolidated notebook; sealed original diary is immutable')
    with journal.batch():
        return _review_game(journal,identifier,annotator=annotator,verdict=verdict,
            value=value,reason=reason,independent=independent)


def _review_game(journal, identifier, *, annotator, verdict, value=None, reason='', independent=False):
    from .score_observer import ScoreObserver
    from datetime import datetime,timezone
    if type(independent) is not bool:raise ValueError('independence attestation must be explicit boolean')
    row=journal.get(identifier);p=row.data['payload']
    if p.get('category')!='score_game_record' or not isinstance(annotator,str) or not annotator.strip():raise ValueError('game and reviewer identity required')
    statuses={'confirm':'confirmed','correct':'corrected','unreadable':'unreadable',
              'insufficient':'insufficient','defer':'pending','disagree':'disputed'}
    if verdict not in statuses:raise ValueError('unsupported review verdict')
    annotation=None
    if verdict in ('confirm','correct','unreadable') and p.get('proposal_id'):
        previous=next((r for r in reversed(journal.category_records('observation','score_human_annotation'))
            if r.data['payload']['proposal_id']==p['proposal_id'] and r.data['payload']['annotator']==annotator),None)
        annotation=ScoreObserver.annotate_review(journal,p['proposal_id'],annotator=annotator,verdict=verdict,
            value=value,reason=reason or 'Reviewer inspected the original photograph',independent=independent,
            supersedes=previous.id if previous else None)
    elif verdict in ('confirm','correct'):raise ValueError('original score photograph unavailable')
    return journal.append('observation',dict(category='score_review_status',attempt_id=p['attempt_id'],
        proposal_id=p.get('proposal_id'),game_record_id=row.id,annotator=annotator,verdict=verdict,status=statuses[verdict],
        annotation_id=annotation.id if annotation else None,reason=reason,
        reviewed_at=datetime.now(timezone.utc).isoformat(),independent_score_certificate=False),
        episode=row.data['episode'],sources=[row.id,*([annotation.id] if annotation else [])],
        producer='human-score-review',version='deferred-review-v1')


def serve_review(journal_path, root=None, port=8769):
    """Existing inspector's loopback review UI; no camera/controller initialization."""
    from http.server import BaseHTTPRequestHandler,HTTPServer
    from memory.evidence import EvidenceJournal
    import secrets
    if (Path(journal_path).parent/'capture-manifest.json').is_file():raise ValueError('sealed original diary cannot be used for review')
    token=secrets.token_urlsafe(24)
    class Handler(BaseHTTPRequestHandler):
        def reply(self,code,body,mime='application/json'):
            raw=body.encode() if isinstance(body,str) else body
            self.send_response(code);self.send_header('Content-Type',mime)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            from urllib.parse import urlparse,parse_qs
            url=urlparse(self.path)
            if url.path=='/':
                page=Path(__file__).with_name('score-review.html').read_text().replace('__REVIEW_TOKEN__',token)
                return self.reply(200,page,'text/html; charset=utf-8')
            j=EvidenceJournal(journal_path)
            try:
                if url.path=='/queue':
                    if root:import_queue(j,root)
                    return self.reply(200,json.dumps(dict(games=queue_rows(j),history=performance_history(j),baselines=baseline_history(j))))
                if url.path=='/image':
                    query=parse_qs(url.query)
                    from .score_observer import ScoreObserver
                    if query.get('game'):
                        game=j.get(query['game'][0]).data['payload'];index=int(query.get('frame',['-1'])[0])
                        originals=game.get('additional_originals',[])
                        if game.get('category')!='score_game_record' or not 0<=index<len(originals):raise ValueError('recorded supporting frame required')
                        artifact=originals[index];path=Path(artifact['path']);expected=artifact['sha256']
                    else:
                        key=query.get('id',[''])[0];p=j.get(key).data['payload']
                        if p.get('category')!='score_review_proposal':raise ValueError('original proposal required')
                        path=ScoreObserver.review_artifact(j,p);expected=p['artifact']['sha256']
                    raw=path.read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('original image changed')
                    return self.reply(200,raw,'image/png' if path.suffix.lower()=='.png' else 'image/jpeg')
                self.reply(404,b'Not found','text/plain')
            except (ValueError,KeyError,OSError) as exc:self.reply(400,json.dumps(dict(error=str(exc))))
            finally:j.close()
        def do_POST(self):
            if self.path!='/review' or self.headers.get('X-Review-Token')!=token:return self.reply(403,b'Forbidden','text/plain')
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 1<=length<=16384:raise ValueError('bounded review required')
                data=json.loads(self.rfile.read(length));j=EvidenceJournal(journal_path)
                try:r=review_game(j,data.pop('id'),**data)
                finally:j.close()
                self.reply(200,json.dumps(dict(id=r.id)))
            except (ValueError,KeyError,OSError,TypeError) as exc:self.reply(400,json.dumps(dict(error=str(exc))))
        def log_message(self,*unused):pass
    server=HTTPServer(('127.0.0.1',port),Handler)
    print(f'Deferred score review: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    finally:server.server_close()


def performance_history(journal):
    """Existing independent certificates alone admit complete-game averages."""
    from experiments.comparison.robotron import validate_certificates
    from learning.episode_identity import canonical_experience
    from memory.evidence import digest
    import statistics
    experiences={}
    for r in journal.category_records('observation','robotron_evaluation_episode'):
        p=r.data['payload']
        try:
            validate_certificates(journal,p)
            identity=canonical_experience(journal,p['source_episode'])
            values={m['value'] for m in p['score_observations']}
            boundary=journal.get(p['boundary_certificate']).data['payload']
            if p.get('synthetic') or p.get('confirmed_terminal') is not True or len(values)!=1:continue
            if boundary.get('policy')!=p['policy']:continue
            value=values.pop()
            if type(value) is not int or value<0 or not isinstance(p['policy'],str):continue
            row=dict(id=r.id,value=value,experience=identity,policy=p['policy'],
                conditions=p.get('conditions',{}),sequence=r.sequence,
                terminal_timestamp=max(f['timestamp'] for f in boundary['terminal_frames']))
            experiences.setdefault(identity,[]).append(row)
        except (ValueError,KeyError,OSError,TypeError):continue
    groups={}
    for peers in experiences.values():
        # Conflicting relabelings of one capture are not separate policy trials.
        if len({(r['policy'],r['value'],digest(r['conditions'])) for r in peers})!=1:continue
        row=min(peers,key=lambda r:r['sequence']);groups.setdefault(row['policy'],[]).append(row)
    result={}
    for policy,rows in groups.items():
        rows.sort(key=lambda r:r['sequence'])
        rolling={}
        for n in (10,30):
            batch=rows[-n:]
            if len(batch)<n or len({digest(r['conditions']) for r in batch})!=1:rolling[str(n)]=None;continue
            values=[r['value'] for r in batch]
            rolling[str(n)]=dict(mean=statistics.mean(values),standard_deviation=statistics.stdev(values),
                standard_error=statistics.stdev(values)/(n**.5),count=n,record_ids=[r['id'] for r in batch],
                uncertainty='descriptive complete-game batch; no causal improvement inferred')
        result[policy]=dict(qualified_games=len(rows),records=rows,rolling=rolling,
            order='durable evidence sequence; capture clocks are not comparable across sessions',
            exclusions='duplicates, conflicts, uncertified games and mixed-condition rolling batches')
    return result


def freeze_baseline(journal,name,policy,record_ids):
    """Freeze a reproducible qualified collection; grant no gameplay authority."""
    from memory.evidence import digest
    import statistics
    if not isinstance(name,str) or not name.strip() or not record_ids or len(record_ids)!=len(set(record_ids)):
        raise ValueError('named distinct qualified baseline games required')
    available={r['id']:r for r in performance_history(journal).get(policy,{}).get('records',[])}
    if any(i not in available for i in record_ids):raise ValueError('baseline requires independently qualified games of one policy')
    rows=[available[i] for i in record_ids]
    if len({digest(r['conditions']) for r in rows})!=1:raise ValueError('baseline conditions must remain frozen')
    prior=[r for r in journal.category_records('observation','score_baseline_snapshot') if r.data['payload']['name']==name]
    if prior:
        if prior[-1].data['payload']['record_ids']!=record_ids or prior[-1].data['payload']['policy']!=policy:
            raise ValueError('named frozen baseline cannot be replaced')
        return prior[-1]
    values=[r['value'] for r in rows]
    return journal.append('observation',dict(category='score_baseline_snapshot',name=name,policy=policy,
        record_ids=record_ids,records=rows,collection_sha256=digest(rows),conditions=rows[0]['conditions'],
        mean=statistics.mean(values),standard_deviation=statistics.stdev(values) if len(values)>1 else None,
        count=len(rows),physical_authorization=False,
        uncertainty='frozen descriptive collection; prospective independent comparison still required'),
        episode='qualified-score-history',producer='existing-comparison',version='deferred-score-history-v1')


def baseline_history(journal):
    """Original snapshot remains frozen even if a certificate later fails."""
    current=performance_history(journal)
    result=[]
    for row in journal.category_records('observation','score_baseline_snapshot'):
        p=row.data['payload'];available={r['id'] for r in current.get(p['policy'],{}).get('records',[])}
        result.append(dict(id=row.id,**p,currently_qualified=all(i in available for i in p['record_ids'])))
    return result


if __name__=="__main__":main()
