"""Compile/execute production framing, auth and TCP bridge with host UART stubs."""
from pathlib import Path
import argparse
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--sanitizers',default='undefined')
args=parser.parse_args()
with tempfile.TemporaryDirectory(prefix='elegoo-s3-host-') as directory:
    for name,source,extra in [('framing','framing.cpp',[]),('auth','auth.cpp',[]),('power-loss','power_loss.cpp',[]),
                              ('bridge-closed','bridge.cpp',[]),('bridge-forwarding','bridge.cpp',['-DCHARLIE_ENABLE_MOTOR_FORWARDING=1'])]:
        target=Path(directory)/name
        command=['g++','-std=c++17','-Wall','-Wextra','-Werror','-pedantic','-fsanitize='+args.sanitizers,
                 '-I'+str(root/'tests'/'stubs'),*extra,str(root/'tests'/source)]
        if source=='bridge.cpp':command.append(str(root/'ElegooS3Camera'/'MotorBridge.cpp'))
        subprocess.run([*command,'-o',str(target)],check=True)
        subprocess.run([str(target)],check=True,timeout=15)
        print(name+': passed')
