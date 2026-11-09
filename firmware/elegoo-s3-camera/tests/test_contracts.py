import hashlib
import json
from pathlib import Path
import re
import subprocess
root=Path(__file__).resolve().parents[1]
sketch=root/'ElegooS3Camera'

def test_unmodified_upstream_assets_and_pins():
    manifest=json.loads((root/'upstream-manifest.json').read_text())
    assert manifest['commit']=='a92013016d2386cd4ed2e0e7893b018f04b89cfc'
    for name in ['camera_pins.h','camera_index.h','camera_index.html']:
        assert hashlib.sha256((sketch/name).read_bytes()).hexdigest()==manifest['files'][name]

def test_legacy_camera_routes_and_single_uart_writer():
    source=(sketch/'app_httpd.cpp').read_text()
    for route in ['/', '/status','/control','/capture','/stream','/Test','/test1','/test2','/keypress','/json_command']:
        assert re.search(r'\.uri\s*=\s*"'+re.escape(route)+'"',source)
    executable=re.sub(r'/\*.*?\*/|//[^\n]*','',source,flags=re.S)
    assert not re.search(r'Serial2\.(print|write)',executable)
    writers=[]
    for path in sketch.glob('*'):
        if path.suffix in ('.cpp','.h','.ino'):
            code=re.sub(r'/\*.*?\*/|//[^\n]*','',path.read_text(),flags=re.S)
            writers.extend([path.name]*len(re.findall(r'Serial2\.(?:print|write)\s*\(',code)))
    assert writers==['MotorBridge.cpp']
    assert '#define CHARLIE_ENABLE_MOTOR_FORWARDING 0' in (sketch/'MotorBridge.h').read_text()

def test_one_wifi_owner_no_provisioning_uart_or_credentials():
    camera=(sketch/'CameraWebServer_AP.cpp').read_text()
    assert 'WiFi.mode' not in camera and 'WiFi.softAP' not in camera
    server=(sketch/'ProvisioningServer.cpp').read_text()
    assert 'Serial2' not in server and 'MotorBridge' not in server
    assert 'httpd_ssl_start' in server and 'HTTPD_SSL_TRANSPORT_INSECURE' not in server
    assert 'confirmOnTarget' in (sketch/'NetworkRuntime.cpp').read_text()
    for path in sketch.glob('*'):
        if path.suffix in ('.cpp','.h','.ino','.html'):
            content=path.read_text()
            assert not re.search(r'(?:const )?char\s*\*?\s*(?:password|ssid)\s*=\s*"',content)
            assert 'charlie_home_wifi' not in content and 'BEGIN PRIVATE KEY-----\n' not in content

def test_public_asset_generation_is_reproducible():
    before=(sketch/'SetupAssets.h').read_bytes()
    subprocess.run(['python3',str(root/'tools'/'embed_assets.py')],check=True)
    assert (sketch/'SetupAssets.h').read_bytes()==before

def test_partition_geometry_matches_original_layout():
    rows=[line.split(',') for line in (sketch/'partitions.csv').read_text().splitlines() if line and not line.startswith('#')]
    assert [(r[0],int(r[3],16),int(r[4],16)) for r in rows]==[
        ('nvs',0x9000,0x5000),('otadata',0xe000,0x2000),('app0',0x10000,0x330000),
        ('app1',0x340000,0x330000),('spiffs',0x670000,0x180000),('coredump',0x7f0000,0x10000)]
