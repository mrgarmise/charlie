#!/usr/bin/env python3
"""Install a menu application; pin Charlie Eyes to Mint's panel via its menu."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--host',default='five@charlie.local')
    ap.add_argument('--project',default='Projects/charlie')
    args=ap.parse_args()
    directory=Path.home()/'.local/share/charlie-eyes';directory.mkdir(parents=True,exist_ok=True)
    launcher=directory/'launcher.py'
    shutil.copyfile(Path(__file__).with_name('charlie_eyes_launcher.py'),launcher)
    # Desktop Exec has its own quoting rules, not shell expansion. Escape its
    # reserved literals and double literal percent field-code characters.
    def quote(s):
        return '"'+str(s).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'
    command=' '.join(quote(s) for s in ('/usr/bin/python3',launcher,'--host',args.host,'--project',args.project))
    applications=Path.home()/'.local/share/applications';applications.mkdir(parents=True,exist_ok=True)
    desktop=applications/'charlie-eyes.desktop'
    desktop.write_text('[Desktop Entry]\nType=Application\nName=Charlie Eyes\nComment=Passive camera, tracks and agency evidence\n'+
        'Exec='+command+'\nIcon=camera-photo\nTerminal=false\nCategories=Utility;\nStartupNotify=false\n')
    desktop.chmod(0o755)
    if shutil.which('update-desktop-database'):subprocess.run(['update-desktop-database',str(applications)],check=False)
    print('Installed Charlie Eyes. Find it in the Mint menu; right-click → Add to panel. Closing its window releases the viewer and idle camera.')


if __name__=='__main__':main()
