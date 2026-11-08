"""Recover hash-bound existing reviews/photos from saved archives, never label.

Offline only. Does not extract arbitrary archive paths or open original journals.
The output is a fresh working snapshot with the existing image-location overlay.
Diagnostic reviews remain diagnostic; this is not a training corpus or accuracy.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tarfile


def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def recover(audit_archive, image_archives, output):
    output=Path(output)
    if output.exists():raise FileExistsError('preserve earlier recovery output')
    output.mkdir(parents=True)
    with tarfile.open(audit_archive) as archive:
        candidates=[m for m in archive if m.isfile() and m.name.endswith('/score-review-audit.json')]
        if len(candidates)!=1 or candidates[0].size>16*1024*1024:
            raise ValueError('one bounded score-review audit required')
        audit=json.load(archive.extractfile(candidates[0]))
        expected=audit['sha256']
        member=archive.getmember(candidates[0].name.rsplit('/',1)[0]+'/sqlite/'+expected+'.sqlite3')
        if not member.isfile() or member.size>256*1024*1024:raise ValueError('bounded review snapshot required')
        snapshot=archive.extractfile(member).read()
        if hashlib.sha256(snapshot).hexdigest()!=expected:raise ValueError('review snapshot integrity mismatch')
    (output/'learning-evidence.sqlite3').write_bytes(snapshot)
    # Existing validator is the only authority on effective review status,
    # supersession, independence and partitions. Never reconstruct annotations.
    from memory.evidence import EvidenceJournal
    from experiments.ppal.score_feedback import reviewed_labels
    journal=EvidenceJournal(output/'learning-evidence.sqlite3',read_only=True)
    try:
        annotations=journal.category_records('observation','score_human_annotation')
        targets={r.data['payload']['artifact_sha256'] for r in annotations}
        sources=[];locations={};matches=[]
        for path in image_archives:
            counts=Counter()
            with tarfile.open(path) as archive:
                for member in archive:
                    counts['members']+=1
                    suffix=Path(member.name).suffix.lower()
                    if not member.isfile() or suffix not in ('.png','.jpg','.jpeg'):continue
                    counts['image_members']+=1
                    if member.size>32*1024*1024:
                        counts['oversize_images_rejected']+=1;continue
                    with archive.extractfile(member) as stream:
                        h=hashlib.sha256()
                        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
                    key=h.hexdigest()
                    if key not in targets:continue
                    counts['annotation_hash_matches']+=1
                    matches.append(dict(archive_sha256=sha_file(path),member=member.name,sha256=key))
                    if key not in locations:
                        from PIL import Image
                        with archive.extractfile(member) as stream:
                            image=Image.open(stream);image.verify()
                        folder=output/'images';folder.mkdir(exist_ok=True)
                        target=folder/(key+suffix)
                        with archive.extractfile(member) as stream:target.write_bytes(stream.read())
                        locations[key]=str(target.relative_to(output))
            sources.append(dict(path=Path(path).name,sha256=sha_file(path),**counts))
        (output/'image-locations.json').write_text(json.dumps(locations,indent=2)+'\n')
        partitions={}
        for partition in ('training','validation','final','diagnostic'):
            rows,excluded=reviewed_labels(journal,partition=partition)
            partitions[partition]=dict(eligible=len(rows),
                proposal_ids=[r['proposal_id'] for r in rows],
                exclusions=excluded)
        result=dict(schema='charlie-score-archive-recovery-v1',
            audit_archive_sha256=sha_file(audit_archive),review_snapshot_sha256=expected,
            annotation_records=len(annotations),distinct_annotation_photos=len(targets),
            recovered_annotation_photos=len(locations),missing_annotation_photos=sorted(targets-set(locations)),
            partitions=partitions,image_archives=sources,matches=matches,
            qualification='existing consulted reviews; original partitions unchanged; no invented labels',
            original_journal_modified=False,model_trained=False,hef_generated=False)
        (output/'recovery.json').write_text(json.dumps(result,indent=2)+'\n')
        if sha_file(output/'learning-evidence.sqlite3')!=expected:
            raise ValueError('read-only review snapshot changed')
        return result
    finally:journal.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit-archive',type=Path,required=True)
    p.add_argument('--image-archive',type=Path,action='append',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(recover(a.audit_archive,a.image_archive,a.output),indent=2))


if __name__=='__main__':main()
