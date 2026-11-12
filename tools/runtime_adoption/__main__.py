"""Read-only integration and promotion planning. No apply/install/enable command."""
import argparse
import json
from .inventory import collect
from .promotion import load,validate,plan,release_candidate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    inv=sub.add_parser('inventory');inv.add_argument('--baseline',required=True);inv.add_argument('--candidate',required=True)
    inv.add_argument('--ops',required=True);inv.add_argument('--protected',action='append',default=[])
    for action in ('plan','release-manifest'):
        command=sub.add_parser(action);command.add_argument('--manifest',required=True)
    check=sub.add_parser('validate');check.add_argument('--manifest',required=True);check.add_argument('--inventory',required=True)
    check.add_argument('--receipts',required=True);check.add_argument('--stage',choices=('source','master','release','enablement'),default='source')
    check.add_argument('--ability',action='append',default=[]);check.add_argument('--approval');check.add_argument('--trust-key');check.add_argument('--trust-key-sha256');check.add_argument('--source-root',required=True)
    a=p.parse_args()
    if a.action=='inventory':result=collect(a.baseline,a.candidate,a.ops,a.protected)
    elif a.action=='plan':result=plan(load(a.manifest))
    elif a.action=='release-manifest':result=release_candidate(load(a.manifest))
    else:
        result=validate(load(a.manifest),load(a.inventory),load(a.receipts),stage=a.stage,selected=a.ability,
            approval=load(a.approval) if a.approval else None,key_path=a.trust_key,key_sha256=a.trust_key_sha256,source_root=a.source_root)
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=='__main__':main()
