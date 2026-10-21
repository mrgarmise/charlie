"""Host wrapper software fixtures; no native readiness or gameplay claims."""
import json
import time
from pathlib import Path
from hashlib import sha256
import xml.etree.ElementTree as ET

import pytest
from tools import native_robotron_trial as runner


def safe():
    return dict(temperature_c=50.,throttled=0,available_memory_bytes=1024**3,
        rss_bytes=100*1024**2,free_disk_bytes=10*1024**3,
        worker_pids=[100],device_owners={'/dev/video0':[100]})


@pytest.mark.parametrize('field,value',[
    ('temperature_c',75.),('temperature_c',float('nan')),('throttled',1),
    ('available_memory_bytes',1),('rss_bytes',769*1024**2),
    ('free_disk_bytes',1),('device_owners',{'/dev/video0':[999]})])
def test_resource_and_ownership_stops(field,value):
    row=safe();assert runner.stop_reason(row) is None
    row[field]=value
    assert runner.stop_reason(row)


def review(tmp_path):
    prior=json.loads((runner.ROOT/'docs/validation/native-integration-20261021/test-report.json').read_text())
    names=[r['test'] for r in prior['full_run']['failed_cases'] if 'Operation not permitted' in r['message']]
    xml=ET.Element('testsuites');suite=ET.SubElement(xml,'testsuite')
    for name in names:
        cls,test=name.split('::',1);ET.SubElement(suite,'testcase',classname=cls,name=test)
    receipt=tmp_path/'synthetic-checks.xml';ET.ElementTree(xml).write(receipt)
    note=tmp_path/'fixture-review.txt';note.write_text('SYNTHETIC HOST REVIEW; not an operator/native receipt')
    proofs={k:dict(path=str(note),sha256=runner.checksum(note)) for k in runner.PROOFS}
    proofs['software_tests']=dict(path=str(receipt),sha256=runner.checksum(receipt))
    doc=dict(runtime_revision='fixture-revision',reviewed_at=time.time(),
        host_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),proofs=proofs)
    path=tmp_path/'review.json';path.write_text(json.dumps(doc))
    return path,doc


def test_review_exact_runtime_all_sockets_and_proof_integrity(tmp_path):
    path,doc=review(tmp_path)
    assert runner.verify_review(path,'fixture-revision')==doc
    with pytest.raises(ValueError,match='exact runtime'):
        runner.verify_review(path,'other-revision')
    Path(doc['proofs']['camera_ownership']['path']).write_text('changed')
    with pytest.raises(ValueError,match='changed'):
        runner.verify_review(path,'fixture-revision')


def test_blocked_socket_receipt_cannot_arm(tmp_path):
    path,doc=review(tmp_path)
    receipt=Path(doc['proofs']['software_tests']['path']);tree=ET.parse(receipt)
    ET.SubElement(next(tree.iter('testcase')),'failure',message='Operation not permitted')
    tree.write(receipt);doc['proofs']['software_tests']['sha256']=runner.checksum(receipt)
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match='must pass'):
        runner.verify_review(path,'fixture-revision')


def test_expired_review_cannot_arm(tmp_path):
    path,doc=review(tmp_path);doc['reviewed_at']-=3601;path.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match='fresh same-boot'):
        runner.verify_review(path,'fixture-revision')


def test_monitoring_failure_stops_owned_process_without_retry(tmp_path,monkeypatch):
    path,doc=review(tmp_path)
    real_read=Path.read_text
    monkeypatch.setattr(Path,'read_text',lambda p,*a,**kw:'systemd\n' if str(p)=='/proc/1/comm' else real_read(p,*a,**kw))
    monkeypatch.setattr(runner.subprocess,'check_output',lambda cmd,**kw:'fixture-revision\n' if cmd[1:]==['rev-parse','HEAD'] else '')
    rows=[dict(safe(),monotonic=1.,cpu_ticks=0)]
    def sample(*a,**kw):
        if rows:return rows.pop()
        raise OSError('lost telemetry')
    monkeypatch.setattr(runner,'sample',sample)
    children=[];stopped=[]
    class Child:
        pid=100;returncode=None
        def __init__(self,*a,**kw):children.append(self)
        def poll(self):return self.returncode
    monkeypatch.setattr(runner.subprocess,'Popen',Child)
    def stop(child):stopped.append(child);child.returncode=-2;return True
    monkeypatch.setattr(runner,'stop_process',stop)
    output=tmp_path/'trial'
    monkeypatch.setattr(runner.sys,'argv',['runner','--run','--expected-revision','fixture-revision',
        '--review',str(path),'--output',str(output)])
    with pytest.raises(SystemExit):runner.main()
    assert len(children)==1 and stopped==children
    result=json.loads((output/'runner-result.json').read_text())
    assert 'lost telemetry' in result['reason'] and result['automatic_restart'] is False
    assert (output/'identity.json').exists() and (output/'native-resources.jsonl').exists()
