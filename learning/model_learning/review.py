"""Portable, offline review through the existing immutable DatasetStore API."""
import base64
from collections import Counter, defaultdict
import io
import json
from pathlib import Path
from PIL import Image
from memory.evidence import digest
from .data import sha, fingerprints


def coverage(data):
    rows = data.rows()
    matrix = defaultdict(Counter)
    pairs = []
    for i, row in enumerate(rows):
        matrix[row['session']][row['label'] or 'unreviewed'] += 1
        for other in rows[:i]:
            if (int(row['dhash'], 16) ^ int(other['dhash'], 16)).bit_count() <= 4:
                pairs.append([other['observation_id'], row['observation_id']])
    return dict(class_by_session={k: dict(v) for k, v in sorted(matrix.items())},
                near_duplicate_pairs=pairs, partitions=dict(Counter(r['effective_partition'] or 'unassigned' for r in rows)),
                requirements='Whole sessions; every known class in train/validation/test; default final test >=5 per class including reviewed unknown; no cross-split dHash distance <=4.')


def _binding(data):
    # Original observation IDs bind a packet to this evidence set without exposing local paths.
    return digest(dict(task=data.task, observations=sorted(r['observation_id'] for r in data.rows())))


def export_gallery(data, destination, *, on_progress=None):
    from .robotron import frame, incumbent
    rows = data.rows()
    cards = []
    for row in rows:
        if on_progress: on_progress()
        if row['effective_partition'] == 'test':
            continue  # Do not repeatedly expose sealed final holdouts or predictions.
        if sha(row['path']) != row['sha256'] or fingerprints(row['path'])[0] != row['pixel_sha256']:
            raise ValueError('observation integrity changed')
        with Image.open(row['path']) as image:
            thumbnail = image.convert('RGB'); thumbnail.thumbnail((640, 480))
            stream = io.BytesIO(); thumbnail.save(stream, format='JPEG')
        cards.append(dict(observation_id=row['observation_id'], sha256=row['sha256'],
                          label_id=row['label_id'], confirmed=row['label'], session=row['session'],
                          source=row['provenance'], proposed=incumbent(frame(row)),
                          image='data:image/jpeg;base64,'+base64.b64encode(stream.getvalue()).decode()))
    packet = dict(schema='charlie-review-v1', task=data.task, binding=_binding(data), rows=cards)
    # Escape HTML script delimiters even inside JSON strings. All rendering uses textContent.
    encoded = json.dumps(packet).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    page = '''<!doctype html><meta charset="utf-8"><title>Charlie evidence review</title>
<style>body{font:16px sans-serif;max-width:1100px;margin:auto}article{border:1px solid #aaa;padding:1em;margin:1em 0}img{max-width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}select,input{font:inherit;margin:.4em}button{font:inherit;padding:.8em}</style>
<h1>Charlie Robotron review</h1><p>Review actual screen content. Machine proposals are fallible, never ground truth. Leave uncertain images unreviewed. Unknown means a genuinely out-of-domain or indeterminate screen, not merely classifier abstention. Existing confirmed labels remain unless you explicitly select a replacement. No partitions or model activation are performed here.</p>
<label>Your reviewer name <input id="reviewer" maxlength="256"></label><label>Review reason <input id="reason" maxlength="2000" value="Visual review of historical camera photograph"></label>
<button id="save">Download reviews.json</button><p id="message"></p><main id="cards"></main>
<script id="packet" type="application/json">PACKET</script><script>
const packet=JSON.parse(document.getElementById('packet').textContent), choices=[];
for(const row of packet.rows){const a=document.createElement('article'),im=document.createElement('img'),p=document.createElement('pre'),s=document.createElement('select');im.src=row.image;
p.textContent=JSON.stringify({id:row.observation_id,session:row.session,confirmed:row.confirmed,machine_proposal:row.proposed,source:row.source},null,2);
for(const v of ['', 'title_menu','gameplay','terminal','unknown']){const o=document.createElement('option');o.value=v;o.textContent=v||'Leave unchanged / unreviewed';s.append(o)}
a.append(im,p,s);document.getElementById('cards').append(a);choices.push([row,s]);}
document.getElementById('save').onclick=()=>{const reviewer=document.getElementById('reviewer').value.trim(),reason=document.getElementById('reason').value.trim();if(!reviewer||!reason){document.getElementById('message').textContent='Enter your own reviewer name and reason.';return}
const rows=choices.filter(([r,s])=>s.value).map(([r,s])=>({observation_id:r.observation_id,sha256:r.sha256,label_id:r.label_id,label:s.value}));
if(!rows.length)return;const result={schema:packet.schema,task:packet.task,binding:packet.binding,reviewer,reason,rows};const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='reviews.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
</script>'''.replace('PACKET', encoded)
    destination = Path(destination)
    with destination.open('x', encoding='utf-8') as output:
        output.write(page)
    return dict(path=str(destination), shown=len(cards), binding=packet['binding'], coverage=coverage(data))


def import_reviews(data, path):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('review byte budget exceeded')
    packet = json.loads(path.read_text())
    receipt_key = digest(packet)
    prior = [r for r in data.events('model_review_import') if r.data['payload']['packet_digest'] == receipt_key]
    if prior:
        return dict(status='ALREADY_IMPORTED', receipt=prior[-1].id)
    if packet.get('schema') != 'charlie-review-v1' or packet.get('task') != data.task or packet.get('binding') != _binding(data):
        raise ValueError('review packet belongs to a different evidence set; export a fresh gallery')
    for key, limit in (('reviewer', 256), ('reason', 2000)):
        if not isinstance(packet.get(key), str) or not packet[key].strip() or len(packet[key]) > limit:
            raise ValueError('bounded attributed review required')
    reviews = packet.get('rows')
    if not isinstance(reviews, list) or not 1 <= len(reviews) <= 256:
        raise ValueError('bounded nonempty review batch required')
    current = {r['observation_id']: r for r in data.rows()}
    seen = set()
    # Validate the ENTIRE batch before any append. Existing label IDs implement explicit supersession.
    for review in reviews:
        identifier = review['observation_id']
        row = current.get(identifier)
        if identifier in seen or row is None or row['effective_partition'] == 'test':
            raise ValueError('duplicate, foreign or sealed observation')
        seen.add(identifier)
        if review['sha256'] != row['sha256'] or review['label_id'] != row['label_id']:
            raise ValueError('stale review; export a fresh gallery')
        if review['label'] not in data.labels or sha(row['path']) != row['sha256'] or fingerprints(row['path'])[0] != row['pixel_sha256']:
            raise ValueError('invalid label or changed observation')
    with data.journal.batch():
        labels = [data.label(r['observation_id'], r['label'], reviewer=packet['reviewer'], reason=packet['reason'], supersedes=r['label_id']).id for r in reviews]
        receipt = data.append('model_review_import', dict(packet_digest=receipt_key, count=len(labels)), sources=labels)
    return dict(status='IMPORTED', receipt=receipt.id, count=len(labels))
