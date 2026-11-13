"""Offline, read-only comparison. Never opens a device or scans credential partitions."""
import argparse
import hashlib
import json
from pathlib import Path

STOCK_SHA256='c196e9077be06b3f61f6acfcf66219fe0535b60ae1d26183c43b2de80ff25c5b'
IMAGE_SHA256='1f0075a5e922908bd11907ab8595ee8c000b4be981b34f9b58fc131ca2892b3c'
APP_OFFSET=0x10000
APP_SLOT=0x330000

def digest(data):
    return hashlib.sha256(data).hexdigest()

def compare_image(backup, image):
    if not image or len(image)>APP_SLOT or APP_OFFSET+len(image)>len(backup):
        raise ValueError('image/backup bounds rejected')
    return {'image_bytes':len(image),'image_sha256':digest(image),
            'backup_offset':hex(APP_OFFSET),
            'exact_bytes_equal':backup[APP_OFFSET:APP_OFFSET+len(image)]==image}

def compare_sources(left, right):
    # Explicit public source allowlist; no config, credential files or raw contents.
    report={}
    for name in ('ESP32_CameraServer_AP_2023_V1.3.ino','CameraWebServer_AP.cpp',
                 'CameraWebServer_AP.h','app_httpd.cpp','camera_index.h','camera_pins.h'):
        a=(left/name).read_bytes();b=(right/name).read_bytes()
        report[name]={'left_sha256':digest(a),'right_sha256':digest(b),'byte_equal':a==b,
                      'lf_equal':a.replace(b'\r\n',b'\n')==b.replace(b'\r\n',b'\n')}
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-backup',type=Path,required=True)
    parser.add_argument('--public-image',type=Path,required=True)
    parser.add_argument('--public-source',type=Path,required=True)
    parser.add_argument('--umrt-source',type=Path,required=True)
    args=parser.parse_args()
    # Open regular files only. No serial, reset, networking, NVS decoding or writes.
    for path in (args.stock_backup,args.public_image):
        if not path.is_file():raise SystemExit('regular input file required')
    backup=args.stock_backup.read_bytes();image=args.public_image.read_bytes()
    if len(backup)!=8388608 or digest(backup)!=STOCK_SHA256:
        raise SystemExit('preserved known stock backup identity rejected; no metadata emitted')
    if len(image)!=2960064 or digest(image)!=IMAGE_SHA256:
        raise SystemExit('pinned public stock image identity rejected')
    print(json.dumps({'backup_bytes':len(backup),'backup_sha256':digest(backup),
                      'app0_comparison':compare_image(backup,image),
                      'public_vs_umrt_sources':compare_sources(args.public_source,args.umrt_source)},indent=2))

if __name__=='__main__':main()
