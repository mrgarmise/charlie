"""Local lab state only. Original sources and Charlie's notebook are never opened writable."""
from contextlib import contextmanager
import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path

DEFAULT_CLASSES = ['player','grunt','hulk','tank','human','brain','spheroid','enforcer','quark','electrode']


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as s:
        for b in iter(lambda:s.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


class Lab:
    def __init__(self, root):
        self.root=Path(root).expanduser().resolve()
        if any((p/'learning-evidence.sqlite3').exists() for p in [self.root,*self.root.parents]):
            raise ValueError('Use a separate Vision Lab state directory, never the Executive notebook')
        self.root.mkdir(parents=True,exist_ok=True)
        for n in ('thumbs','pixels','datasets','jobs','models','evaluations'):(self.root/n).mkdir(exist_ok=True)
        with self.connect() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS items(kind TEXT,id TEXT,payload TEXT,PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS frames(id TEXT PRIMARY KEY,source TEXT,locator TEXT,signature TEXT,payload TEXT);
            CREATE TABLE IF NOT EXISTS annotations(frame TEXT,revision INTEGER,payload TEXT,PRIMARY KEY(frame,revision));
            CREATE TRIGGER IF NOT EXISTS annotation_immutable_update BEFORE UPDATE ON annotations BEGIN SELECT RAISE(ABORT,'immutable annotation');END;
            CREATE TRIGGER IF NOT EXISTS annotation_immutable_delete BEFORE DELETE ON annotations BEGIN SELECT RAISE(ABORT,'immutable annotation');END;
            CREATE TABLE IF NOT EXISTS partitions(pixel_sha TEXT PRIMARY KEY,role TEXT,session TEXT);
            CREATE TABLE IF NOT EXISTS consulted_tests(pixel_sha TEXT PRIMARY KEY,evaluation TEXT);
            ''')
        if not self.get('settings','classes',optional=True):self.put('settings','classes',DEFAULT_CLASSES)

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.root/'lab.sqlite3',timeout=20)
        c.execute('PRAGMA busy_timeout=20000')
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def put(self,kind,identifier,value,*,immutable=False):
        with self.connect() as c:
            if immutable:c.execute('INSERT INTO items VALUES(?,?,?)',(kind,identifier,canonical(value)))
            else:c.execute('INSERT OR REPLACE INTO items VALUES(?,?,?)',(kind,identifier,canonical(value)))
        return value

    def get(self,kind,identifier,optional=False):
        with self.connect() as c:r=c.execute('SELECT payload FROM items WHERE kind=? AND id=?',(kind,identifier)).fetchone()
        if r is None:
            if optional:return None
            raise KeyError('Unknown '+kind+' identifier')
        return json.loads(r[0])

    def items(self,kind):
        with self.connect() as c:return [dict(id=i,data=json.loads(p)) for i,p in c.execute('SELECT id,payload FROM items WHERE kind=? ORDER BY rowid',(kind,))]

    def frame(self,identifier):
        with self.connect() as c:r=c.execute('SELECT payload FROM frames WHERE id=?',(identifier,)).fetchone()
        if not r:raise KeyError('Unknown frame identifier')
        return json.loads(r[0])

    def frames(self,source=None):
        with self.connect() as c:
            rows=c.execute('SELECT payload FROM frames'+(' WHERE source=?' if source else '')+' ORDER BY rowid',([source] if source else []))
            return [json.loads(r[0]) for r in rows]

    def save_frame(self,value):
        with self.connect() as c:c.execute('INSERT OR REPLACE INTO frames VALUES(?,?,?,?,?)',(value['id'],value['source_id'],value['locator'],value['signature'],canonical(value)))

    def annotation(self,frame):
        with self.connect() as c:r=c.execute('SELECT payload FROM annotations WHERE frame=? ORDER BY revision DESC LIMIT 1',(frame,)).fetchone()
        return json.loads(r[0]) if r else dict(frame_id=frame,revision=0,boxes=[],status='unreviewed',note='',negative=False)

    def history(self,frame):
        with self.connect() as c:return [json.loads(p) for p, in c.execute('SELECT payload FROM annotations WHERE frame=? ORDER BY revision',(frame,))]

    def annotate(self,frame_id,document):
        import math
        frame=self.frame(frame_id)
        if not frame.get('pixel_sha'):raise ValueError('Load and verify source pixels before annotation')
        allowed=self.get('settings','classes');boxes=document.get('boxes',[])
        if not isinstance(boxes,list) or len(boxes)>500:raise ValueError('At most 500 objects required')
        status=document.get('status','draft')
        if status not in ('draft','review','verified','excluded'):raise ValueError('Invalid review status')
        reviewer=document.get('reviewer','')
        if not isinstance(reviewer,str):raise ValueError('Human reviewer identity must be text')
        reviewer=reviewer.strip()
        if not reviewer or len(reviewer)>120:raise ValueError('Human reviewer identity required')
        clean=[]
        for b in boxes:
            if not isinstance(b,dict):raise ValueError('Object annotation required')
            numbers=[b.get(k) for k in ('x','y','w','h','confidence')]
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in numbers):raise ValueError('Finite box coordinates/confidence required')
            x,y,w,h,conf=numbers
            if not (0<=x<frame['width'] and 0<=y<frame['height'] and w>0 and h>0 and x+w<=frame['width']+.01 and y+h<=frame['height']+.01 and 0<=conf<=1):raise ValueError('Box outside source image')
            name=b.get('class_name')
            if name not in allowed and name!='unknown':raise ValueError('Unconfigured class')
            if type(b.get('uncertain',False)) is not bool or type(b.get('accepted',False)) is not bool:raise ValueError('Boolean uncertainty/acceptance required')
            if status=='verified' and (name=='unknown' or b.get('uncertain') or not b.get('accepted')):raise ValueError('Explicitly accept/correct every box; unresolved objects cannot be ground truth')
            clean.append(dict(x=x,y=y,w=w,h=h,class_name=name,confidence=conf,uncertain=b.get('uncertain',False),accepted=b.get('accepted',False),origin=b.get('origin','human'),model_id=b.get('model_id')))
        if status=='verified' and not boxes and document.get('negative') is not True:raise ValueError('Explicitly confirm an empty/negative frame')
        note=document.get('note','')
        if not isinstance(note,str) or len(note)>5000:raise ValueError('Bounded annotation note required')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT MAX(revision) FROM annotations WHERE frame=?',(frame_id,)).fetchone()
            previous=row[0] or 0
            if type(document.get('revision')) is not int or document['revision']!=previous:raise ValueError('Annotation changed in another tab; reload before saving')
            value=dict(frame_id=frame_id,pixel_sha=frame['pixel_sha'],revision=previous+1,boxes=clean,status=status,reviewer=reviewer,note=note,negative=document.get('negative') is True,at=time.time(),source_provenance=frame['provenance'])
            value['digest']=digest(value)
            c.execute('INSERT INTO annotations VALUES(?,?,?)',(frame_id,previous+1,canonical(value)))
        return value

    def set_classes(self,names):
        if not isinstance(names,list) or not 1<=len(names)<=100 or len(set(names))!=len(names) or any(not isinstance(n,str) or not n.strip() or len(n)>80 or n=='unknown' for n in names):raise ValueError('1..100 distinct nonempty labels; unknown is reserved')
        self.put('settings','classes',names)


def identifier():return uuid.uuid4().hex
