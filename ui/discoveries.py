"""Read-only projection; never open or write the Executive's journal."""
import html
import json
from pathlib import Path


def read_status(state):
    if state is None:return dict(mode='disabled',counts={},questions=[])
    path=Path(state)/'development-status.json'
    if path.stat().st_size>2*1024*1024:raise ValueError('status exceeds bound')
    doc=json.loads(path.read_text())
    return doc.get('consultations') or dict(mode='disabled',counts={},questions=[])


def render(status):
    esc=lambda value:html.escape(str(value),quote=True)
    cards=[]
    for q in status['questions']:
        result=q.get('result',{})
        cards.append('<article><h2>'+esc(q['question'])+'</h2><p>'+esc(q['status'])+
            ' · unverified hypothesis</p><p>'+esc(result.get('answer','Awaiting independent advice'))+
            '</p><p>Origin: '+esc(result.get('origin','none'))+' · model '+esc(result.get('model','none'))+
            ' · latency '+esc(result.get('latency_seconds','unknown'))+'</p><p>Follow-up: '+
            esc(result.get('follow_up','Independent observation or human review'))+'</p><p>Evidence: '+
            esc(', '.join(q['evidence_ids']))+'</p></article>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Questions &amp; Discoveries</title>'
        '<h1>Questions &amp; Discoveries</h1><p>'+esc(status['mode'])+'</p><p>'+esc(status['counts'])+
        '</p><p>Advice is fallible and grants no authority. Verified count remains zero until independent qualification exists.</p>'+
        ''.join(cards)+'</html>').encode()
