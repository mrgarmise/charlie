"""Root-scoped local and SFTP readers; selective cache, never a remote shell."""
import contextlib
import fnmatch
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import warnings
import zipfile
import tarfile
from PIL import Image, ImageOps
from .store import digest,identifier,file_hash

IMAGES={'.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'}
VIDEOS={'.mp4','.avi','.mkv','.mov','.webm'}
MAX_BYTES=32*1024**2
MAX_PIXELS=20_000_000


def relative(name):
    p=PurePosixPath(name)
    if not isinstance(name,str) or '\\' in name or '\x00' in name or p.is_absolute() or any(x in ('..','.') for x in name.split('/')) or not name:
        raise ValueError('Unsafe relative source path')
    return p


class LocalReader:
    def __init__(self,source):self.root=Path(source['root']).resolve(strict=True);self.excludes=source['excludes']
    def __enter__(self):return self
    def __exit__(self,*unused):pass
    def walk(self):
        for root,dirs,files in os.walk(self.root,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(root)/d).is_symlink() and not any(fnmatch.fnmatch((Path(root)/d).relative_to(self.root).as_posix()+'/',e) for e in self.excludes)]
            for f in files:
                p=Path(root)/f
                if p.is_symlink():continue
                s=p.stat()
                if stat.S_ISREG(s.st_mode):yield p.relative_to(self.root).as_posix(),dict(size=s.st_size,mtime_ns=s.st_mtime_ns)
    @contextlib.contextmanager
    def open(self,name):
        parts=relative(name).parts
        fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
        try:
            for part in parts[:-1]:
                new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=new
            leaf=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
            with os.fdopen(leaf,'rb') as s:yield s
        finally:os.close(fd)
    def local_path(self,name):
        p=self.root/relative(name)
        if p.is_symlink() or not p.resolve().is_relative_to(self.root):raise ValueError('Unsafe container path')
        if any(x.is_symlink() for x in [p,*p.parents] if x!=self.root and x.is_relative_to(self.root)):raise ValueError('Symlink source denied')
        return p


class SFTPReader:
    def __init__(self,source):self.source=source
    def __enter__(self):
        import paramiko
        s=self.source;self.client=paramiko.SSHClient();self.client.load_system_host_keys()
        known=Path.home()/'.ssh/known_hosts'
        if known.exists():self.client.load_host_keys(str(known))
        self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
        options=dict(hostname=s['host'],username=s['user'],port=s.get('port',22),timeout=10,banner_timeout=10,auth_timeout=15,allow_agent=True,look_for_keys=True)
        cfg=Path.home()/'.ssh/config'
        if cfg.exists():
            config=paramiko.SSHConfig.from_path(str(cfg)).lookup(s['host'])
            if config.get('proxycommand') or config.get('proxyjump'):raise ValueError('ProxyJump/ProxyCommand not executed; use the existing mounted SFTP source')
            options['hostname']=config.get('hostname',options['hostname'])
            if config.get('identityfile'):options['key_filename']=[str(Path(p).expanduser()) for p in config['identityfile']]
        try:
            self.client.connect(**options);self.sftp=self.client.open_sftp();self.root=self.sftp.normalize(s['root']).rstrip('/') or '/'
            self.sftp.get_channel().settimeout(20)
            return self
        except BaseException:self.client.close();raise
    def __exit__(self,*unused):self.client.close()
    def walk(self):
        pending=[''];count=0
        while pending:
            rel=pending.pop();folder=self.root+'/'+rel
            for a in self.sftp.listdir_attr(folder):
                name=(rel+'/'+a.filename).lstrip('/');relative(name);count+=1
                if any(fnmatch.fnmatch(name+'/',e) or fnmatch.fnmatch(name,e) for e in self.source['excludes']):continue
                if count>100000:raise ValueError('Remote entry limit reached; configure a narrower root')
                if stat.S_ISLNK(a.st_mode):continue
                if stat.S_ISDIR(a.st_mode):pending.append(name)
                elif stat.S_ISREG(a.st_mode):yield name,dict(size=a.st_size,mtime_ns=int(a.st_mtime*1e9))
    @contextlib.contextmanager
    def open(self,name):
        relative(name);p=self.root+'/'+name
        if stat.S_ISLNK(self.sftp.lstat(p).st_mode):raise ValueError('Remote symlink denied')
        actual=self.sftp.normalize(p)
        if not actual.startswith(self.root.rstrip('/')+'/'):raise ValueError('Remote path outside configured root')
        with self.sftp.open(actual,'rb') as s:yield s


def reader(source):return LocalReader(source) if source['kind']=='local' else SFTPReader(source)


def add_source(lab,document):
    kind=document.get('kind','local');root=document.get('root','')
    if kind not in ('local','sftp'):raise ValueError('Local or SFTP source required')
    if not isinstance(root,str) or not root or '\x00' in root:raise ValueError('Source root required')
    if kind=='local':
        path=Path(root).expanduser().resolve()
        if path==lab.root or lab.root.is_relative_to(path) or path.is_relative_to(lab.root):raise ValueError('Lab state must be outside all source roots')
        root=str(path)
    elif not root.startswith('/') or '..' in PurePosixPath(root).parts or str(PurePosixPath(root))=='/':raise ValueError('Absolute scoped remote root required')
    if kind=='sftp' and (not re.fullmatch(r'[A-Za-z0-9_.-]+',document.get('host','')) or not re.fullmatch(r'[A-Za-z0-9_.-]+',document.get('user',''))):raise ValueError('Safe SSH host/user required')
    excludes=document.get('excludes',['.git/**','**/.git/**','**/__pycache__/**'])
    if not isinstance(excludes,list) or len(excludes)>100 or any(not isinstance(x,str) or len(x)>300 for x in excludes):raise ValueError('Bounded exclusion patterns required')
    depth=document.get('group_depth',1)
    if type(depth) is not int or not 0<=depth<=10:raise ValueError('Grouping depth 0..10 required')
    auth=document.get('authenticity','unknown')
    if auth not in ('unknown','operator-declared-authentic','synthetic-fixture'):raise ValueError('Explicit authenticity category required')
    source=dict(id=identifier(),kind=kind,root=root,name=str(document.get('name') or Path(root).name)[:120],group_depth=depth,excludes=excludes,authenticity=auth,at=time.time(),read_only=True)
    if kind=='sftp':
        port=document.get('port',22)
        if type(port) is not int or not 1<=port<=65535:raise ValueError('Invalid SSH port')
        source.update(host=document['host'],user=document['user'],port=port)
    return lab.put('sources',source['id'],source,immutable=True)


def decode(raw,page=0):
    with warnings.catch_warnings():
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(raw)) as im:
            if im.width*im.height>MAX_PIXELS:raise ValueError('Image pixel budget exceeded')
            im.seek(page)
            return ImageOps.exif_transpose(im).convert('RGB').copy()


def pixel_digest(image):return hashlib.sha256(str(image.size).encode()+image.tobytes()).hexdigest()


def raw_bytes(r,locator,member=None,archive_kind=None):
    with r.open(locator) as stream:
        if member:
            relative(member)
            if archive_kind=='tar':
                with tarfile.open(fileobj=stream,mode='r:*') as z:
                    info=z.getmember(member)
                    if not info.isfile() or info.size>MAX_BYTES:raise ValueError('Unsafe TAR image')
                    with z.extractfile(info) as s:return s.read(MAX_BYTES+1)
            with zipfile.ZipFile(stream) as z:
                info=z.getinfo(member)
                if info.file_size>MAX_BYTES or info.file_size/max(1,info.compress_size)>200:raise ValueError('Unsafe compressed image')
                return z.read(info)
        raw=stream.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('Image byte budget exceeded')
        return raw


def store_pixels(lab,frame,image,raw_sha):
    sha=pixel_digest(image)
    frame.update(width=image.width,height=image.height,pixel_sha=sha,source_sha256=raw_sha)
    out=lab.root/'pixels'/(sha+'.png')
    if not out.exists():
        temporary=out.with_name(identifier()+'.tmp');image.save(temporary,format='PNG')
        try:os.link(temporary,out)
        except FileExistsError:pass
        finally:temporary.unlink(missing_ok=True)
    with Image.open(out) as cached:
        if pixel_digest(cached.convert('RGB'))!=sha:raise ValueError('Existing pixel cache is corrupt')
    frame['cache_sha256']=file_hash(out)
    thumb=image.copy();thumb.thumbnail((480,320));thumb.save(lab.root/'thumbs'/(frame['id']+'.jpg'))
    lab.save_frame(frame)
    return frame


def hydrate(lab,frame_id):
    frame=lab.frame(frame_id);source=lab.get('sources',frame['source_id'])
    if frame.get('pixel_sha') and (lab.root/'pixels'/(frame['pixel_sha']+'.png')).is_file():
        p=lab.root/'pixels'/(frame['pixel_sha']+'.png')
        actual=file_hash(p)
        if frame.get('cache_sha256') and actual!=frame['cache_sha256']:raise ValueError('Cached observation integrity mismatch')
        if not frame.get('cache_sha256'):
            with Image.open(p) as im:
                if pixel_digest(im.convert('RGB'))!=frame['pixel_sha']:raise ValueError('Cached observation integrity mismatch')
            frame['cache_sha256']=actual;lab.save_frame(frame)
        return frame
    with reader(source) as r:
        if frame.get('video_index') is not None:
            import cv2
            cap=cv2.VideoCapture(str(r.local_path(frame['locator'])))
            try:
                cap.set(cv2.CAP_PROP_POS_FRAMES,frame['video_index']);ok,arr=cap.read()
                if not ok:raise ValueError('Video frame cannot be decoded')
                im=Image.fromarray(cv2.cvtColor(arr,cv2.COLOR_BGR2RGB))
                return store_pixels(lab,frame,im,frame['container_sha256'])
            finally:cap.release()
        raw=raw_bytes(r,frame['locator'],frame.get('member'),frame.get('archive_kind'));im=decode(raw,frame.get('page',0))
        raw_sha=hashlib.sha256(raw).hexdigest()
        if frame.get('source_sha256') and raw_sha!=frame['source_sha256']:raise ValueError('Original observation changed since indexing; reindex')
        return store_pixels(lab,frame,im,raw_sha)


def index_source(lab,source_id,*,cancel=lambda:False,progress=lambda **kw:None):
    source=lab.get('sources',source_id);warnings_list=[];counts=dict(discovered=0,new=0,unchanged=0,failed=0)
    existing={f['id']:f for f in lab.frames(source_id)}
    def admit(locator,meta,member=None,page=0,video_index=None,raw=None,video_time=None,container_sha=None,archive_kind=None):
        signature=digest(dict(stat=meta,member=member,page=page,video_index=video_index));fid=digest(dict(source=source_id,locator=locator,signature=signature))
        counts['discovered']+=1
        if fid in existing:counts['unchanged']+=1;return
        parts=PurePosixPath(locator).parts[:-1];group='/'.join(parts[:source['group_depth']]) or 'root'
        frame=dict(id=fid,source_id=source_id,locator=locator,signature=signature,member=member,page=page,video_index=video_index,
            session=source_id+':'+group,episode='/'.join(parts) or 'root',metadata=meta,
            timestamp=video_time if video_time is not None else meta['mtime_ns']/1e9,
            timestamp_basis='video-relative offset' if video_time is not None else 'file mtime; not verified capture timing',
            provenance=dict(source_id=source_id,root=source['root'],kind=source['kind'],locator=locator,member=member,page=page,authenticity=source['authenticity'],independently_qualified=False),
            pixel_sha=None,indexed_at=time.time(),container_sha256=container_sha,archive_kind=archive_kind)
        if raw is not None:
            im=decode(raw,page);frame.update(width=im.width,height=im.height,pixel_sha=pixel_digest(im),source_sha256=hashlib.sha256(raw).hexdigest())
            thumb=im.copy();thumb.thumbnail((480,320));thumb.save(lab.root/'thumbs'/(fid+'.jpg'))
        lab.save_frame(frame);counts['new']+=1
    try:
        with reader(source) as r:
            for name,meta in r.walk():
                if cancel():raise InterruptedError('Discovery cancelled')
                if any(fnmatch.fnmatch(name,e) for e in source['excludes']):continue
                suffix=PurePosixPath(name).suffix.lower()
                try:
                    if suffix in IMAGES:
                        signature=digest(dict(stat=meta,member=None,page=0,video_index=None));fid=digest(dict(source=source_id,locator=name,signature=signature))
                        if fid in existing:counts['unchanged']+=1;counts['discovered']+=1;continue
                        if meta['size']>MAX_BYTES:raise ValueError('Image byte budget exceeded')
                        raw=raw_bytes(r,name) if source['kind']=='local' else None
                        admit(name,meta,raw=raw)
                        if raw and suffix in ('.tif','.tiff'):
                            with Image.open(io.BytesIO(raw)) as im:
                                for page in range(1,min(im.n_frames,16)):admit(name,meta,page=page,raw=raw)
                    elif suffix=='.zip':
                        if source['kind']!='local':warnings_list.append(name+': remote container detected; use a mounted/local source for member access');continue
                        with r.open(name) as stream,zipfile.ZipFile(stream) as z:
                            infos=z.infolist()
                            if len(infos)>5000:raise ValueError('Archive member limit exceeded')
                            for info in infos:
                                if info.is_dir():continue
                                relative(info.filename)
                                if stat.S_ISLNK(info.external_attr>>16):raise ValueError('Archive symlink denied')
                                if PurePosixPath(info.filename).suffix.lower() not in IMAGES:continue
                                if info.file_size>MAX_BYTES or info.file_size/max(1,info.compress_size)>200:raise ValueError('Unsafe compressed member')
                                admit(name,meta,member=info.filename,raw=z.read(info))
                    elif suffix in ('.tar','.gz','.tgz'):
                        if source['kind']!='local':warnings_list.append(name+': remote TAR detected; mount/copy selected container first');continue
                        with r.open(name) as stream,tarfile.open(fileobj=stream,mode='r:*') as z:
                            for count,info in enumerate(z):
                                if count>=5000:raise ValueError('TAR member limit exceeded')
                                if info.isdir():continue
                                relative(info.name)
                                if not info.isfile():raise ValueError('TAR links/devices denied')
                                if PurePosixPath(info.name).suffix.lower() not in IMAGES:continue
                                if info.size>MAX_BYTES:raise ValueError('TAR member byte budget exceeded')
                                with z.extractfile(info) as s:raw=s.read(MAX_BYTES+1)
                                admit(name,meta,member=info.name,raw=raw,archive_kind='tar')
                    elif suffix in VIDEOS:
                        if source['kind']!='local':warnings_list.append(name+': remote video detected; mount/copy selectively for sampled decoding');continue
                        import cv2
                        cap=cv2.VideoCapture(str(r.local_path(name)))
                        try:
                            total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS)
                            if total<=0 or not fps>0:raise ValueError('Unsupported video metadata')
                            container_sha=file_hash(r.local_path(name))
                            for number in range(0,min(total,64*30),30):admit(name,meta,video_index=number,video_time=number/fps,container_sha=container_sha)
                        finally:cap.release()
                    elif suffix in ('.tar','.gz','.jsonl','.json'):
                        warnings_list.append(name+': structured/container metadata detected; source paths remain explicit; use ZIP or decoded image directory')
                except (OSError,ValueError,Image.DecompressionBombError,Image.DecompressionBombWarning,EOFError,zipfile.BadZipFile,tarfile.TarError) as e:
                    counts['failed']+=1;warnings_list.append(name+': '+str(e))
                progress(**counts)
                if counts['discovered']>100000:raise ValueError('Frame index limit reached')
    except (OSError,ValueError,ImportError) as e:warnings_list.append('Source inaccessible: '+str(e))
    result=dict(counts=counts,warnings=warnings_list[:500],at=time.time(),source_id=source_id,remote_hashes='pending selective fetch' if source['kind']=='sftp' else 'verified during decode')
    lab.put('indexes',source_id,result)
    return result
