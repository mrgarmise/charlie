"""Build-only pinned S3 candidate; no upload, serial, flash or network configuration."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shlex
import struct
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
EXPECTED=[('nvs',0x9000,0x5000),('otadata',0xe000,0x2000),('app0',0x10000,0x330000),
          ('app1',0x340000,0x330000),('spiffs',0x670000,0x180000),('coredump',0x7f0000,0x10000)]

def validate_binary(binary,partition):
    image=Path(binary).read_bytes()
    if not 24<=len(image)<=0x330000 or image[0]!=0xe9 or int.from_bytes(image[12:14],'little')!=9:
        raise ValueError('S3 application header or active-slot fit rejected')
    table=Path(partition).read_bytes();entries=[]
    types=[(1,2),(1,0),(0,16),(0,17),(1,130),(1,3)]
    for offset in range(0,len(table)-31,32):
        magic,kind,subtype,start,size,label,flags=struct.unpack('<HBBII16sI',table[offset:offset+32])
        if magic!=0x50aa:break
        if len(entries)>=6 or (kind,subtype)!=types[len(entries)] or flags!=0:
            raise ValueError('partition type/subtype/flags changed')
        entries.append((label.rstrip(b'\0').decode(),start,size))
    if entries!=EXPECTED:raise ValueError('partition geometry differs from original layout')
    return dict(image_bytes=len(image),image_sha256=hashlib.sha256(image).hexdigest(),
                slot_bytes=0x330000,slot_remaining=0x330000-len(image),partitions=entries,
                flash_mode=image[2],flash_frequency_code=image[3]&15,flash_size_code=image[3]>>4)

def source_digest():
    digest=hashlib.sha256()
    for path in sorted((root/'ElegooS3Camera').iterdir()):
        if path.is_file():digest.update(path.name.encode()+b'\0'+path.read_bytes())
    return digest.hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli',default='arduino-cli');parser.add_argument('--config-file')
    parser.add_argument('--arduino-data',required=True);parser.add_argument('--build-dir',required=True)
    parser.add_argument('--psram',choices=['opi','qspi'],default='opi');parser.add_argument('--clean',action='store_true')
    args=parser.parse_args();build=Path(args.build_dir).resolve();build.mkdir(parents=True,exist_ok=True)
    data=Path(args.arduino_data).resolve()
    core=data/'packages/esp32/hardware/esp32/2.0.17'
    if not core.is_dir():raise SystemExit('pinned esp32:esp32@2.0.17 must be installed first')
    cli=[args.cli]+(['--config-file',args.config_file] if args.config_file else [])
    fqbn='esp32:esp32:esp32s3:FlashSize=8M,PartitionScheme=default_8MB,PSRAM='+('opi' if args.psram=='opi' else 'enabled')+',USBMode=hwcdc,CDCOnBoot=cdc,FlashMode=qio'
    command=[*cli,'compile','--verbose','--fqbn',fqbn,'--build-path',str(build),
             '--build-property','compiler.cpp.extra_flags=-std=gnu++17']
    if args.clean:command.append('--clean')
    command.append(str(root/'ElegooS3Camera'))
    before=source_digest()
    log=build.parent/(build.name+'-compile.log')
    with log.open('w') as stream:subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=True)
    binary=build/'ElegooS3Camera.ino.bin';partitions=build/'ElegooS3Camera.ino.partitions.bin'
    report=validate_binary(binary,partitions)
    esptool=data/'packages/esp32/tools/esptool_py/4.5.1/esptool.py'
    imageinfo=subprocess.check_output([sys.executable,str(esptool),'--chip','esp32s3','image_info',str(binary)],text=True)
    if 'Checksum:' not in imageinfo or '(invalid)' in imageinfo or 'Validation Hash:' not in imageinfo:
        raise ValueError('esptool integrity verification failed')
    (build/'image-info.txt').write_text(imageinfo)
    if source_digest()!=before:raise ValueError('source changed during compile; discard this build')
    gcc=data/'packages/esp32/tools/xtensa-esp32s3-elf-gcc/esp-2021r2-patch5-8.4.0/bin/xtensa-esp32s3-elf-g++'
    report.update(fqbn=fqbn,core='2.0.17',host=platform.machine(),psram_candidate=args.psram,
        cli_version=subprocess.check_output([*cli,'version'],text=True).strip(),
        compiler_version=subprocess.check_output([str(gcc),'--version'],text=True).splitlines()[0],
        compile_command=shlex.join(command),compile_log=str(log),binary=str(binary),
        source_sha256=before,upstream_commit='a92013016d2386cd4ed2e0e7893b018f04b89cfc',
        core_parent='b71cd3dd917b83aff3b643795a76dab3ac5b42ed',
        not_hardware_qualified=True,deployed=False,motor_forwarding_policy="per-command-hmac-bounded-qualified-pi",
        motor_forwarding_default="closed-without-authenticated-command")
    (build/'build-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
