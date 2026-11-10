"""Compile/execute production framing, auth and TCP bridge with host UART stubs."""
from pathlib import Path
import argparse
import subprocess
import tempfile
import ctypes.util
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--sanitizers',default='undefined')
parser.add_argument('--no-sockets',action='store_true',help='Run deterministic suites in sandboxes denying OS sockets')
args=parser.parse_args()
with tempfile.TemporaryDirectory(prefix='elegoo-s3-host-') as directory:
    for name,source,extra in [('framing','framing.cpp',[]),('auth','auth.cpp',[]),('power-loss','power_loss.cpp',[]),
                              ('bridge-authenticated','bridge.cpp',[]),('command-gate','command_gate.cpp',[]),
                              ('bridge-timing','bridge_timing.cpp',[]),('vendor-uno-timer','vendor_uno_timer.cpp',[]),
                              ('owner-uno-timer','owner_uno_timer.cpp',[]),('owner-uno-protocol','owner_uno_protocol.cpp',[])]:
        if args.no_sockets and source=='bridge.cpp':continue
        target=Path(directory)/name
        command=['g++','-std=c++17','-Wall','-Wextra','-Werror','-pedantic','-fsanitize='+args.sanitizers,
                 '-I'+str(root/'tests'/'stubs'),*extra,str(root/'tests'/source)]
        if source=='bridge_timing.cpp':command.insert(1,'-I'+str(root/'tests'/'stubs-memory'))
        if source in ('bridge.cpp','bridge_timing.cpp'):command.append(str(root/'ElegooS3Camera'/'MotorBridge.cpp'))
        if source in ('bridge.cpp','bridge_timing.cpp','command_gate.cpp'):
            library=ctypes.util.find_library('mbedcrypto')
            if not library:raise RuntimeError('host mbedTLS crypto library required')
            command.append('-l:'+library)
        subprocess.run([*command,'-o',str(target)],check=True)
        subprocess.run([str(target)],check=True,timeout=15)
        print(name+': passed')
