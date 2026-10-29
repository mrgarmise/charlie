"""Resolve only reviewed additive conflicts in a disposable detached CI checkout.

Keep PR #13 application/deployment ownership intact. Never run on a named branch.
"""
import os
from pathlib import Path
import subprocess
import sys


def combine_main(ours,feature):
    anchor="    p.add_argument('--learning-state'"
    flag=next(line for line in feature.splitlines() if "p.add_argument('--model-learning'," in line)
    offline='    if args.offline:\n        run('
    if ours.count(anchor)!=1 or ours.count(offline)!=1 or '--model-learning' in ours:
        raise ValueError('unreviewed application conflict')
    result=ours.replace(anchor,flag+'\n'+anchor,1)
    return result.replace(offline,'    if args.model_learning:\n        kwargs["model_learning"]=True\n'+offline,1)


def combine_deployment(ours,feature):
    start=feature.index('    def activate_perception_shadow(')
    anchor='    def active(self,target):'
    stop=feature.index(anchor,start)
    if ours.count(anchor)!=1 or 'def activate_perception_shadow(' in ours:
        raise ValueError('unreviewed deployment conflict')
    return ours.replace(anchor,feature[start:stop]+anchor,1)


def main(feature_ref):
    if os.environ.get('GITHUB_ACTIONS')!='true' or subprocess.run(['git','symbolic-ref','-q','HEAD'],capture_output=True).returncode==0:
        raise RuntimeError('only a disposable detached CI checkout is supported')
    conflicts=subprocess.check_output(['git','diff','--name-only','--diff-filter=U'],text=True).splitlines()
    allowed={'main.py':combine_main,'learning/deployment.py':combine_deployment}
    if not conflicts or set(conflicts)-set(allowed): raise ValueError('unexpected integration conflict; preserve it for review')
    results={}
    for path in conflicts:
        ours=subprocess.check_output(['git','show',':2:'+path],text=True)
        feature=subprocess.check_output(['git','show',feature_ref+':'+path],text=True)
        results[path]=allowed[path](ours,feature)
    # Validate every conflict before writing any result.
    for path,result in results.items():
        compile(result,path,'exec')
    for path,result in results.items():
        Path(path).write_text(result)
        subprocess.run(['git','add','--',path],check=True)

if __name__=='__main__':main(sys.argv[1])
