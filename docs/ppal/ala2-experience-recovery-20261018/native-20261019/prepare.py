from pathlib import Path
import json, shutil, hashlib
ROOT=Path('/home/five/ala2-recovery-20261019')
AUDIT=Path('/home/five/charlie-e1-probe/audit/2026-10-18-ala2')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
sources={'primary':Path('/home/five/.local/share/charlie/development'),
         'overnight':Path('/home/five/charlie-overnight-20261016T015459Z/validation-state'),
         'scores':Path('/home/five/.local/share/charlie/score-review')}
manifest={}
for name,source in sources.items():
    assert not any(source.rglob('*-wal')) and not any(source.rglob('*-journal'))
    before={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
    dest=ROOT/'preserved'/name
    shutil.copytree(source,dest)
    assert before=={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
    assert before=={str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()}
    manifest[name]={'source':str(source),'files':before}
(ROOT/'preservation.json').write_text(json.dumps(manifest,indent=2))
shutil.copytree(ROOT/'preserved'/'primary',ROOT/'working')
games=json.loads((AUDIT/'canonical-game-manifest.json').read_text())
unlinked=[g for g in games if not g['context_ids']]
(ROOT/'unlinked.json').write_text(json.dumps(unlinked,indent=2))
print('copies verified; unlinked',len(unlinked))
for g in unlinked: print(g['paths'][0])
