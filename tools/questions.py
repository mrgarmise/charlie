"""Explicit-source generalized question selection. Does not start models/sensors."""
import argparse
from contextlib import closing
import json
from pathlib import Path
from learning.question_selection import discover, QuestionQueue
from memory.evidence import EvidenceJournal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['list','inspect','explain','queue','skip','defer','select','show-answer','pending-evaluation','consult'])
    p.add_argument('--source',action='append',default=[])
    p.add_argument('--approval',type=Path);p.add_argument('--runtime-lock',type=Path);p.add_argument('--id');p.add_argument('--notebook',type=Path);p.add_argument('--reason',default='operator selection')
    a=p.parse_args()
    if a.action in ('list','inspect','explain'):
        report=discover(a.source)
        if a.id:report['candidates']=[q for q in report['candidates'] if q['id']==a.id]
        print(json.dumps(report,indent=2));return
    if not a.notebook:p.error('--notebook required; choose a NEW separate decision journal')
    if a.notebook.resolve() in [Path(s).resolve() for s in a.source]:p.error('notebook must differ from sources')
    with closing(EvidenceJournal(a.notebook)) as j:
        q=QuestionQueue(j)
        if a.action=='queue':
            report=discover(a.source)
            if report['errors']:raise ValueError('source reconciliation failed')
            for item in report['candidates']:
                if item['eligible'] and (a.id is None or a.id==item['id']):q.queue(item)
        elif a.action=='consult':
            if not a.id or not a.approval or not a.runtime_lock or not a.source:
                p.error('consult requires --id --source --approval --runtime-lock; external safe-idle trial only')
            from learning.meditation_consultation import MeditationConsultations, ManualApprovalSlot
            c=MeditationConsultations(q,a.source,ManualApprovalSlot(a.approval,a.runtime_lock),enabled=True)
            c.refresh()
            c.on_meditation('manual-'+a.id,selected_id=a.id)
        elif a.action in ('skip','defer','select'):q.decide(a.id,a.action,a.reason)
        states=q.states()
        if a.action=='pending-evaluation':states={k:v for k,v in states.items() if v['state']=='awaiting-evaluation'}
        if a.id:states={k:v for k,v in states.items() if k==a.id}
        print(json.dumps(states,indent=2))

if __name__=='__main__':main()
