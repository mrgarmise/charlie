"""Read-only continuation acceptance; never commission an Executive turn."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from learning.continuity import compare_restart


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    args=p.parse_args()
    print(json.dumps(compare_restart(json.loads(args.before.read_text()),json.loads(args.after.read_text())),indent=2))
