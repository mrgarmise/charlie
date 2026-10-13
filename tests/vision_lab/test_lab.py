"""Deterministic synthetic controls. No authentic labels, SSH host or hardware exercised."""
import io
import json
from pathlib import Path
import socket
import threading
import time
import zipfile
import pytest
from PIL import Image
from vision_lab.store import Lab,file_hash,digest
from vision_lab.sources import add_source,index_source,hydrate,relative,LocalReader
from vision_lab.datasets import freeze,export_zip,export_yolo,quality,split_sessions
from vision_lab.demo import create
from vision_lab.evaluation import measure


@pytest.fixture
def dataset(tmp_path):return create(tmp_path/'fixtures')


def test_discovery_incremental_hashes_formats_and_corruption(tmp_path):
    root=tmp_path/'originals';root.mkdir();lab=Lab(tmp_path/'state')
    for extension in ['png','jpg','webp','bmp','tiff']:Image.new('RGB',(20,30),(14,80,150)).save(root/('image.'+extension))
    (root/'bad.png').write_text('not an image');(root/'skip').mkdir();Image.new('RGB',(4,4)).save(root/'skip'/'ignored.png')
    s=add_source(lab,dict(root=str(root),excludes=['skip/**'],authenticity='synthetic-fixture'))
    before={p.name:file_hash(p) for p in root.iterdir() if p.is_file()}
    result=index_source(lab,s['id']);assert result['counts']['new']==5 and result['counts']['failed']==1
    again=index_source(lab,s['id']);assert again['counts']['unchanged']==5
    assert before=={p.name:file_hash(p) for p in root.iterdir() if p.is_file()}
    png=next(f for f in lab.frames() if f['locator']=='image.png');f=hydrate(lab,png['id']);assert f['width']==20 and f['pixel_sha']
    (lab.root/'pixels'/(f['pixel_sha']+'.png')).write_bytes(b'tampered')
    with pytest.raises(ValueError,match='integrity'):hydrate(lab,f['id'])


def test_missing_source_and_scope_controls(tmp_path):
    lab=Lab(tmp_path/'state');s=add_source(lab,dict(root=str(tmp_path/'absent')))
    assert 'inaccessible' in index_source(lab,s['id'])['warnings'][0]
    with pytest.raises(ValueError):add_source(lab,dict(root=str(tmp_path)))
    for value in ['../image.png','/etc/passwd','a/../../b','a\\b','a\x00b']:
        with pytest.raises(ValueError):relative(value)
    root=tmp_path/'source';root.mkdir();outside=tmp_path/'outside';outside.mkdir();Image.new('RGB',(5,5)).save(outside/'x.png')
    (root/'link').symlink_to(outside,target_is_directory=True)
    s=add_source(lab,dict(root=str(root)));assert not index_source(lab,s['id'])['counts']['new']
    with LocalReader(s) as r:
        with pytest.raises(OSError):
            with r.open('link/x.png'):pass


def test_notebook_and_descendant_state_are_never_written(tmp_path):
    original=tmp_path/'development';original.mkdir();(original/'learning-evidence.sqlite3').write_bytes(b'preserve')
    with pytest.raises(ValueError):Lab(original)
    with pytest.raises(ValueError):Lab(original/'child')
    assert (original/'learning-evidence.sqlite3').read_bytes()==b'preserve' and not (original/'child').exists()


def test_zip_tar_tiff_pages_without_extraction(tmp_path):
    import tarfile
    root=tmp_path/'source';root.mkdir();lab=Lab(tmp_path/'state');buf=io.BytesIO();Image.new('RGB',(10,10),'red').save(buf,format='PNG')
    with zipfile.ZipFile(root/'frames.zip','w') as z:z.writestr('arbitrary/001.png',buf.getvalue())
    with tarfile.open(root/'frames.tar.gz','w:gz') as z:
        info=tarfile.TarInfo('arbitrary/002.png');info.size=len(buf.getvalue());z.addfile(info,io.BytesIO(buf.getvalue()))
    Image.new('RGB',(6,7),'red').save(root/'multi.tiff',save_all=True,append_images=[Image.new('RGB',(6,7),'blue')])
    s=add_source(lab,dict(root=str(root)));r=index_source(lab,s['id']);assert r['counts']['new']==4
    for f in lab.frames():assert hydrate(lab,f['id'])['width'] in (6,10)
    assert not (root/'arbitrary').exists()


@pytest.mark.parametrize('member',['../escape.png','/absolute.png','a/../../x.png'])
def test_unsafe_archive_members_are_rejected(tmp_path,member):
    root=tmp_path/'source';root.mkdir();lab=Lab(tmp_path/'state')
    with zipfile.ZipFile(root/'bad.zip','w') as z:z.writestr(member,b'bad')
    s=add_source(lab,dict(root=str(root)));r=index_source(lab,s['id']);assert r['counts']['failed']==1 and not lab.frames()


def test_immutable_annotation_revision_conflict_history_and_uncertainty(dataset):
    lab,m=dataset;f=lab.frames()[0];a=lab.annotation(f['id']);a['reviewer']='Engineering reviewer';a['boxes'][0]['x']+=1
    update=lab.annotate(f['id'],a);assert update['revision']==2 and len(lab.history(f['id']))==2
    with pytest.raises(ValueError,match='another tab'):lab.annotate(f['id'],a)
    a=lab.annotation(f['id']);a['boxes'][0]['uncertain']=True
    with pytest.raises(ValueError,match='unresolved'):lab.annotate(f['id'],a)
    a['status']='review';lab.annotate(f['id'],a)
    assert quality(lab,[f['id']])['issues']
    with lab.connect() as c:
        with pytest.raises(Exception,match='immutable'):c.execute('DELETE FROM annotations')


def test_model_boxes_need_explicit_acceptance_and_empty_frames_need_confirmation(dataset):
    lab,m=dataset;f=lab.frames()[0];a=lab.annotation(f['id']);a['boxes'][0].update(origin='model',accepted=False,model_id='fixture-candidate')
    with pytest.raises(ValueError):lab.annotate(f['id'],a)
    a['boxes']=[]
    with pytest.raises(ValueError,match='empty'):lab.annotate(f['id'],a)
    a['negative']=True;lab.annotate(f['id'],a)


def test_frozen_versions_labels_exports_and_session_lock(dataset):
    lab,m=dataset;selected=m['selected_frames'];second=freeze(lab,m['name'],selected,m['assignments'])
    assert second['version']==2 and m['digest']!=second['digest']
    a=export_zip(lab,m['id']).read_bytes();b=export_zip(lab,m['id']).read_bytes();assert a==b
    with zipfile.ZipFile(io.BytesIO(a)) as z:
        assert 'path' not in json.loads(z.read('train.yaml')) and 'test' not in json.loads(z.read('train.yaml'))
    bad=dict(m['assignments']);sessions=list(bad);bad[sessions[0]],bad[sessions[1]]=bad[sessions[1]],bad[sessions[0]]
    with pytest.raises(ValueError,match='cannot change'):freeze(lab,'illegal',selected,bad)
    out=export_yolo(lab,m['id']);label=next(out.rglob('*.txt'));label.write_text('tampered')
    with pytest.raises(ValueError,match='integrity'):export_yolo(lab,m['id'])


def test_duplicate_content_cannot_cross_partitions(dataset,tmp_path):
    lab,m=dataset;f=lab.frames()[0];copy=tmp_path/'copy';copy.mkdir();original=Path(lab.get('sources',f['source_id'])['root'])/f['locator'];(copy/'alias.png').write_bytes(original.read_bytes())
    s=add_source(lab,dict(root=str(copy)));index_source(lab,s['id']);alias=lab.frames(s['id'])[0];hydrate(lab,alias['id'])
    a=lab.annotation(f['id']);a['revision']=0;lab.annotate(alias['id'],a)
    selected=m['selected_frames']+[alias['id']];assign=dict(m['assignments']);role=next(r['role'] for r in m['frames'] if r['frame_id']==f['id']);assign[alias['session']]='val' if role!='val' else 'train'
    with pytest.raises(ValueError,match='duplicate'):freeze(lab,'bad',selected,assign)


def test_geometric_metrics_false_positive_missed_and_confusion():
    def box(name,x=0,confidence=.9):return dict(class_name=name,x=x,y=0,w=10,h=10,confidence=confidence)
    rows=[dict(frame_id='fixture',ground_truth=[box('player'),box('grunt',30)],predictions=[box('player'),box('player',30),box('grunt',60)],latency_ms=2.)]
    r=measure(rows,['player','grunt']);assert r['micro']==dict(tp=1,fp=2,fn=1,precision=1/3,recall=.5)
    assert r['per_class']['player']['ap50']==1 and r['per_class']['grunt']['ap50']==0
    assert r['confusion']['grunt → player']==1 and r['error_examples']


def test_root_scoped_sftp_registration_no_credentials(tmp_path):
    lab=Lab(tmp_path/'state')
    for d in [dict(kind='sftp',root='/home/five',host='charlie;rm',user='five'),dict(kind='sftp',root='../outside',host='charlie.local',user='five')]:
        with pytest.raises(ValueError):add_source(lab,d)
    s=add_source(lab,dict(kind='sftp',root='/home/five/Projects/charlie/robotron-runs',host='charlie.local',user='five',password='not stored'))
    assert 'password' not in s and s['read_only']


def test_http_host_csrf_paths_and_real_image(dataset):
    from http.server import ThreadingHTTPServer
    from vision_lab.server import application
    from urllib.request import Request,urlopen
    from urllib.error import HTTPError
    lab,m=dataset
    server=ThreadingHTTPServer(('127.0.0.1',0),application(lab,None,'fixture-token',0));port=server.server_port;server.RequestHandlerClass=application(lab,None,'fixture-token',port)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{port}'
    try:
        assert b'Charlie Vision Lab' in urlopen(url+'/').read()
        for path,headers,body in [('/api/state',{},None),('/api/state',{'Host':'evil.example'},None),('/api/classes',{},b'{"classes":["x"]}'),('/../../etc/passwd',{'X-Vision-Token':'fixture-token'},None)]:
            with pytest.raises(HTTPError):urlopen(Request(url+path,data=body,headers=headers))
        fid=lab.frames()[0]['id'];r=urlopen(Request(url+'/image?frame='+fid,headers={'X-Vision-Token':'fixture-token'}));assert Image.open(io.BytesIO(r.read())).size==(96,96)
        state=json.loads(urlopen(Request(url+'/api/state',headers={'X-Vision-Token':'fixture-token'})).read());assert len(state['frames'])==8
    finally:server.shutdown();server.server_close();thread.join()


def test_sftp_metadata_only_index_selective_transfer_and_scope(tmp_path,monkeypatch):
    import sys,types,stat
    from vision_lab.sources import SFTPReader
    data=io.BytesIO();Image.new('RGB',(8,8),'green').save(data,format='PNG');reads=[]
    class SFTP:
        def normalize(self,p):return p
        def get_channel(self):return types.SimpleNamespace(settimeout=lambda n:None)
        def listdir_attr(self,p):return [types.SimpleNamespace(filename='one.png',st_mode=stat.S_IFREG,st_size=len(data.getvalue()),st_mtime=12)]
        def lstat(self,p):return types.SimpleNamespace(st_mode=stat.S_IFREG)
        def open(self,p,mode):assert mode=='rb';reads.append(p);return io.BytesIO(data.getvalue())
    class Client:
        def load_system_host_keys(self):pass
        def load_host_keys(self,*a):pass
        def set_missing_host_key_policy(self,p):assert p=='reject'
        def connect(self,**options):assert 'password' not in options
        def open_sftp(self):return SFTP()
        def close(self):pass
    monkeypatch.setitem(sys.modules,'paramiko',types.SimpleNamespace(SSHClient=Client,RejectPolicy=lambda:'reject'))
    monkeypatch.setattr(Path,'home',classmethod(lambda cls:tmp_path/'unconfigured-home'))
    lab=Lab(tmp_path/'state');s=add_source(lab,dict(kind='sftp',root='/approved/archive',host='fixture.local',user='tester',authenticity='synthetic-fixture'))
    index_source(lab,s['id']);assert reads==[] and len(lab.frames())==1
    f=hydrate(lab,lab.frames()[0]['id']);assert len(reads)==1 and f['source_sha256']
    hydrate(lab,f['id']);assert len(reads)==1
    with SFTPReader(s) as r:
        with pytest.raises(ValueError):
            with r.open('../outside'):pass


def test_remote_root_must_be_scoped_and_annotation_types_are_bounded(tmp_path):
    lab,m=create(tmp_path/'fixture')
    with pytest.raises(ValueError,match='scoped'):add_source(lab,dict(kind='sftp',root='/',host='charlie.local',user='five'))
    fid=m['frames'][0]['frame_id']
    with pytest.raises(ValueError):lab.annotate(fid,dict(revision=1,reviewer=7,boxes=[]))
    with pytest.raises(ValueError):lab.annotate(fid,dict(revision=1,reviewer='fixture',boxes=['invalid']))
    assert len(lab.history(fid))==1
