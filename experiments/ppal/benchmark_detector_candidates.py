"""Host-only segmentation costs on saved pixels; never recognition or native FPS."""
import argparse
import json
import math
import platform
import statistics
import time
from pathlib import Path
from PIL import Image
from .eyes.sprites import regions
from .projectile_agency import candidates


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repeats',type=int,default=3)
    a=p.parse_args()
    if not 1<=a.repeats<=100: p.error('repeats must be 1..100')
    rows=[]
    for path in sorted(a.root.glob('*.png')):
        with Image.open(path) as image: image=image.convert('RGB')
        for name,fn in [('existing_cpu_regions',regions),('existing_projectile_candidates',candidates)]:
            for repeat in range(a.repeats):
                start=time.perf_counter();fn(image);duration=time.perf_counter()-start
                rows.append(dict(image=path.name,stage=name,seconds=duration,repeat=repeat))
    summary={}
    for stage in sorted({r['stage'] for r in rows}):
        values=sorted(r['seconds'] for r in rows if r['stage']==stage)
        summary[stage]=dict(samples=len(values),median_seconds=statistics.median(values),p95_seconds=values[math.ceil(.95*len(values))-1])
    with a.output.open('x') as f:
        json.dump(dict(native=False,new_gameplay=False,scope='host archived pixels; no recognition-quality or native FPS claim',python=platform.python_version(),summary=summary,samples=rows),f,indent=2)


if __name__=='__main__':main()
