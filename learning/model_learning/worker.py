"""Fixed CPU trainer. OS limits apply before numerical library imports."""
import json
import math
import os
from pathlib import Path
import resource
import sys


def run(config_path):
    config=json.loads(Path(config_path).read_text()); budget=config['proposal']
    resource.setrlimit(resource.RLIMIT_CPU,(budget['cpu_seconds'],budget['cpu_seconds']))
    memory=budget['memory_mb']*1024**2
    resource.setrlimit(resource.RLIMIT_AS,(memory,memory))
    disk=budget['disk_mb']*1024**2
    resource.setrlimit(resource.RLIMIT_FSIZE,(disk,disk))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_NOFILE,(32,32))
    if hasattr(os,'sched_getaffinity'):
        os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    from .robotron import frame,features,predict,PREPROCESSING
    import numpy as np
    rows=config['dataset']['rows']
    if len(rows)>budget['max_frames']: raise ValueError('frame budget exceeded')
    train=[r for r in rows if r['partition']=='train' and r['label']!='unknown']
    centers={label:np.mean([features(frame(r)) for r in train if r['label']==label],axis=0).tolist()
             for label in config['dataset']['labels'] if label!='unknown'}
    model=dict(schema='model-learning-v1',preprocessing=PREPROCESSING,runtime='numpy-cpu-json-v1',centroids=centers,
               radius=.3,margin=.01,dataset_digest=config['dataset_digest'])
    # A single predefined validation-only radius, no holdout-driven tuning.
    validation=[r for r in rows if r['partition']=='validation' and r['label']!='unknown']
    distances=[float(np.sqrt(np.mean((features(frame(r))-np.asarray(centers[r['label']]))**2))) for r in validation]
    model['radius']=min(.3,max(.03,max(distances)*1.1))
    usage=resource.getrusage(resource.RUSAGE_SELF)
    model['worker_resources']=dict(cpu_seconds=usage.ru_utime+usage.ru_stime,peak_rss_kib=usage.ru_maxrss,
        address_space_limit_bytes=resource.getrlimit(resource.RLIMIT_AS)[0],cpu_limit_seconds=resource.getrlimit(resource.RLIMIT_CPU)[0],
        file_limit_bytes=resource.getrlimit(resource.RLIMIT_FSIZE)[0])
    Path('model.json').write_text(json.dumps(model,allow_nan=False))

if __name__=='__main__': run(sys.argv[1])
