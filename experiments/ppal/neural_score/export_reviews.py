"""Read-only portable export of labeled score frames for Mint/DFC training.

SQLite read-only backup includes committed WAL state. Only hash-verified
original human-reviewed images are copied; all original record IDs, timestamps,
proposals, review status and split partitions remain unchanged.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

from memory.evidence import EvidenceJournal
from experiments.ppal.score_observer import ScoreObserver


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def export(journal, output, *, include_unreviewed=False):
    journal=Path(journal).resolve(strict=True)
    output=Path(output).expanduser().resolve()
    if output.exists():
        raise FileExistsError("preserve prior exports; output must not exist")
    if journal.parent.joinpath("capture-manifest.json").is_file():
        raise ValueError("source is a sealed per-game original; export only a working score review journal")
    if output.is_relative_to(journal.parent):
        raise ValueError("export must be outside source journal directory")
    output.mkdir(parents=True)
    copied=output/"learning-evidence.sqlite3"
    source=sqlite3.connect(journal.as_uri()+"?mode=ro",uri=True)
    destination=sqlite3.connect(copied)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    snapshot=EvidenceJournal(copied,read_only=True)
    locations={};missing=[];included=Counter()
    try:
        annotations=snapshot.category_records("observation","score_human_annotation")
        authorized={r.data["payload"]["proposal_id"] for r in annotations}
        proposals=snapshot.category_records("observation","score_review_proposal")
        for r in proposals:
            if not include_unreviewed and r.id not in authorized:
                continue
            p=r.data["payload"]
            try:
                path=ScoreObserver.review_artifact(snapshot,p)
                key=p["artifact"]["sha256"]
                if sha(path)!=key:
                    raise ValueError("original image integrity mismatch")
                if key not in locations:
                    image_dir=output/"images"
                    image_dir.mkdir(exist_ok=True)
                    suffix=path.suffix.lower()
                    if suffix not in (".png",".jpg",".jpeg"):
                        raise ValueError("unrecognized original image format")
                    target=image_dir/(key+suffix)
                    shutil.copyfile(path,target)
                    if sha(target)!=key:
                        raise ValueError("portable copy integrity mismatch")
                    locations[key]=str(target.relative_to(output))
                included[p["partition"]]+=1
            except (OSError,ValueError,KeyError) as exc:
                missing.append(dict(proposal_id=r.id,sha256=p.get("artifact",{}).get("sha256"),
                                    reason=str(exc)))
    finally:
        snapshot.close()
    (output/"image-locations.json").write_text(json.dumps(locations,indent=2)+"\n")
    record=dict(schema="charlie-score-labeled-export-v1",journal_sha256=sha(copied),
                reviewed_annotation_records=len(annotations),photographs=len(locations),
                included_proposals_by_partition=dict(included),missing_or_invalid=missing,
                complete_game_score_certified=False,physical_operations=False,
                original_records_rewritten=False,
                preparation="portable working-journal snapshot; train and evaluate only with original frozen split commitments")
    (output/"export.json").write_text(json.dumps(record,indent=2)+"\n")
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--journal",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--include-unreviewed",action="store_true")
    a=p.parse_args()
    print(json.dumps(export(a.journal,a.output,include_unreviewed=a.include_unreviewed),indent=2))


if __name__=="__main__":
    main()
