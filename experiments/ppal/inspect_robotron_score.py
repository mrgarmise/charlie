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
    args=ap.parse_args()
    from .score_observer import ScoreObserver
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
    # Existing session diary includes attempts without report.json.
    for path in sorted(root.rglob('experiment-evidence.sqlite3')):
        if path.resolve()==journal.path.resolve():continue
        source=EvidenceJournal(path,read_only=True)
        try:journal.merge_from(source)
        finally:source.close()
    for path in sorted(root.rglob('report.json')):
        folder=path.parent
        try:
            parent=json.loads((folder.parent/'session.json').read_text())
            number=next((i+1 for i,g in enumerate(parent.get('games',[])) if Path(g['path']).name==folder.name),None)
        except (OSError,ValueError,KeyError):number=None
        ScoreObserver.queue_game(journal,folder,session=folder.parent,number=number or folder.name)


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
        status=statuses.get(p['attempt_id'],{}).get('status','pending')
        if len({r.data['payload']['value'] for r in peers})>1:status='disputed'
        if proposal:
            p.update(proposed_score=proposal['proposed_score'],confidence=proposal['confidence'],
                timestamp=proposal['timestamp'],terminal_support=proposal['context'].get('terminal_support',False))
        else:p.update(proposed_score=None,confidence=None,timestamp=None,terminal_support=False)
        p.update(review_status=status,review=statuses.get(p['attempt_id']),
            annotations=[dict(id=r.id,**r.data['payload']) for r in peers])
        result.append(p)
    return sorted(result,key=lambda p:(p['session'],str(p['number']).zfill(5)))


def review_game(journal, identifier, *, annotator, verdict, value=None, reason='', independent=False):
    from .score_observer import ScoreObserver
    from datetime import datetime,timezone
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
                    return self.reply(200,json.dumps(dict(games=queue_rows(j),history=performance_history(j))))
                if url.path=='/image':
                    key=parse_qs(url.query).get('id',[''])[0];p=j.get(key).data['payload']
                    if p.get('category')!='score_review_proposal':raise ValueError('original proposal required')
                    path=Path(p['artifact']['path']);raw=path.read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=p['artifact']['sha256']:raise ValueError('original image changed')
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
    """Only existing independent certificates admit complete-game averages."""
    from experiments.comparison.robotron import validate_certificates
    from learning.episode_identity import canonical_experience
    import statistics
    groups={};seen=set()
    for r in journal.category_records('observation','robotron_evaluation_episode'):
        p=r.data['payload']
        try:
            validate_certificates(journal,p)
            identity=canonical_experience(journal,p['source_episode'])
            values={m['value'] for m in p['score_observations']}
            if p.get('confirmed_terminal') is not True or len(values)!=1 or identity in seen:continue
            value=values.pop()
            if type(value) is not int or value<0:continue
            seen.add(identity);groups.setdefault(p['policy'],[]).append(dict(id=r.id,value=value,experience=identity))
        except (ValueError,KeyError,OSError,TypeError):continue
    return {policy:dict(qualified_games=len(rows),records=rows,
        rolling={str(n):dict(mean=statistics.mean([r['value'] for r in rows[-n:]]),
            standard_deviation=statistics.stdev([r['value'] for r in rows[-n:]]),count=n,
            uncertainty='descriptive complete-game batch; no causal improvement inferred') if len(rows)>=n else None for n in (10,30)}) for policy,rows in groups.items()}


if __name__=="__main__":main()
