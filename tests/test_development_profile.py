"""The profiler runs normal entry points with explicitly simulated evidence."""
import json
import subprocess
import sys
from pathlib import Path
from test_normal_learning_lifecycle import experience


def test_profile_runs_offline_and_refuses_to_overwrite_evidence(tmp_path):
    root=experience(tmp_path);out=tmp_path/'benchmark'
    cmd=[sys.executable,'tools/profile_development.py','--episode-root',str(root),'--output',str(out)]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
    assert p.returncode==0,p.stderr
    result=json.loads((out/'benchmark.json').read_text())
    assert result['evidence_unchanged'] and result['checkpoint_result_consistent']
    assert result['completed_analytical_stages']>0
    assert result['independently_qualified_findings']==0
    assert result['physical_authorization'] is False
    assert result['scientific_result_digests']
    original=(out/'benchmark.json').read_bytes()
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
    assert p.returncode!=0 and 'preserve every prior benchmark' in p.stderr
    assert (out/'benchmark.json').read_bytes()==original
