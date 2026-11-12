"""Read-only verification of owner archive and verbatim host-test excerpts."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def verify(archive):
    root=Path(__file__).resolve().parents[1]/'tests'/'fixtures'
    manifest=json.loads((root/'owner_uno_provenance.json').read_text())
    digest=lambda value:hashlib.sha256(value).hexdigest()
    if digest(archive.read_bytes())!=manifest['archive_sha256']:
        raise ValueError('owner archive hash mismatch')
    sources=[]
    with tarfile.open(archive,'r:gz') as bundle:
        for name,expected in manifest['members'].items():
            value=bundle.extractfile(name).read()
            if digest(value)!=expected:raise ValueError('member hash mismatch: '+name)
            sources.append(value.decode('utf-8-sig').replace('\r\n','\n'))
    for name,expected in manifest['fixtures'].items():
        value=(root/name).read_bytes()
        if digest(value)!=expected:raise ValueError('fixture hash mismatch: '+name)
        if not any(value.decode() in source for source in sources):
            raise ValueError('fixture is not an exact normalized source excerpt: '+name)
    print('Owner archive, source members and seven verbatim fixtures verified (read-only).')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    verify(parser.parse_args().archive)
