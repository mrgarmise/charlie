"""Read-only authentic frame inventory; produces no labels or training claims."""
import argparse
import hashlib
import json
from PIL import Image
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path);p.add_argument('--session',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();rows=[]
    for path in sorted(a.root.rglob('*.png')):
        with Image.open(path) as image:
            rgb=image.convert('RGB');pixel=hashlib.sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()
            geometry=rgb.size
        rows.append(dict(path=str(path.relative_to(a.root)),session=a.session,geometry=geometry,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pixel_sha256=pixel,
            human_verified=False,labels=None,timestamp_basis=None))
    result=dict(schema='charlie-labeling-backlog-v1',root=str(a.root),session=a.session,
        images=len(rows),unique_pixels=len({r['pixel_sha256'] for r in rows}),verified_images=0,
        required_review=len(rows),eligible_training_images=0,frames=rows,
        qualification='inventory only; source authenticity requires provenance review')
    with a.output.open('x') as f:json.dump(result,f,indent=2)


if __name__=='__main__':main()
