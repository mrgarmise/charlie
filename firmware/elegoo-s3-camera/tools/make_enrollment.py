"""Generate private, per-device physical enrollment material. Never opens serial.

A name-constrained per-device CA key stays on the operator host; only the leaf
key goes to the device. Output directory is new, owned 0700; all files are 0600.
No secret appears in stdout, argv or tracked source. No flash/NVS image is made.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import subprocess


def generate(directory,device):
    if not re.fullmatch(r'elegoo-[a-f0-9]{12}',device):raise ValueError('verified device ID required')
    directory=Path(directory)
    directory.mkdir(mode=0o700,parents=False,exist_ok=False)
    def run(*arguments):
        subprocess.run(['openssl',*map(str,arguments)],check=True,capture_output=True,timeout=30)
        for path in directory.iterdir():path.chmod(0o600)
    ca_key=directory/'operator-ca.key';ca=directory/'operator-ca.crt'
    key=directory/'device.key';certificate=directory/'device.crt';csr=directory/'device.csr'
    for private in [ca_key,key]:run('genpkey','-algorithm','EC','-pkeyopt','ec_paramgen_curve:P-256','-out',private)
    dns=device+'.local'
    run('req','-new','-x509','-key',ca_key,'-out',ca,'-days','3650','-subj','/CN='+device+' enrollment authority',
        '-addext','basicConstraints=critical,CA:TRUE,pathlen:0','-addext','keyUsage=critical,keyCertSign,cRLSign',
        '-addext','nameConstraints=critical,permitted;DNS:'+dns+',permitted;IP:192.168.4.1/255.255.255.255')
    run('req','-new','-key',key,'-out',csr,'-subj','/CN='+dns)
    extension=directory/'leaf.ext'
    extension.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:'+dns+',IP:192.168.4.1\n')
    extension.chmod(0o600)
    run('x509','-req','-in',csr,'-CA',ca,'-CAkey',ca_key,'-CAcreateserial','-out',certificate,'-days','730','-extfile',extension)
    run('verify','-CAfile',ca,'-verify_hostname',dns,certificate)
    chain=certificate.read_text()+ca.read_text()
    if len(chain.encode())>=2048 or len(key.read_bytes())>=2048:raise ValueError('certificate material exceeds firmware bound')
    enrollment=dict(device_id=device,certificate=chain,private_key=key.read_text(),
                    token=secrets.token_urlsafe(32),recovery_secret=secrets.token_urlsafe(24))
    target=directory/'identity-enrollment.json'
    target.write_text(json.dumps(enrollment,separators=(',',':')));target.chmod(0o600)
    line=directory/'physical-usb-enrollment.txt'
    line.write_text('ENROLL '+target.read_text()+'\n');line.chmod(0o600)
    fingerprint=hashlib.sha256(ssl.PEM_cert_to_DER_cert(certificate.read_text())).hexdigest()
    # Peer Enrollment schema from PR #28: private token never printed.
    peer=directory/device
    peer.write_text(json.dumps(dict(device_id=device,fingerprint=fingerprint,token=enrollment['token'])));peer.chmod(0o600)
    return dict(device_id=device,certificate_sha256=fingerprint,directory=str(directory),
                enrollment_bytes=target.stat().st_size,not_hardware_authorized=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device-id',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(generate(args.output,args.device_id),indent=2))

if __name__=='__main__':main()
