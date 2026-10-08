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
    args=ap.parse_args()
    from .score_observer import ScoreObserver
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


if __name__=="__main__":
    main()
