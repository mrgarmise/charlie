"""Offline CAL-1 profile derivation/qualification/selection. Never opens hardware.

Selection updates the Pi repository only; it does not flash or energize Pico.
"""
import argparse,json
from pathlib import Path
from hardware.neck_calibration import ProfileRepository,derive_candidate,independently_qualify


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository',type=Path,required=True)
    sub=p.add_subparsers(dest='op',required=True)
    d=sub.add_parser('derive');d.add_argument('--evidence',type=Path,required=True)
    d.add_argument('--commissioning',type=Path,required=True);d.add_argument('--id',required=True)
    d.add_argument('--margin',type=float,required=True);d.add_argument('--supersedes',action='append',default=[])
    q=sub.add_parser('qualify');q.add_argument('--candidate',required=True);q.add_argument('--id',required=True)
    q.add_argument('--reviewer',required=True);q.add_argument('--review',type=Path,required=True)
    s=sub.add_parser('select');s.add_argument('--id',required=True)
    a=p.parse_args();repo=ProfileRepository(a.repository)
    if a.op=='derive':
        result=derive_candidate(a.evidence,json.loads(a.commissioning.read_text()),name=a.id,
                                margin=a.margin,supersedes=a.supersedes)
        repo.save(result)
    elif a.op=='qualify':
        result=independently_qualify(repo.read(a.candidate),name=a.id,reviewer=a.reviewer,
                                   evidence=a.review,physical_validation=True)
        repo.save(result)
    else:result=repo.activate(a.id)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
