#!/usr/bin/env python3
"""Mint-owned browser + SSH lifetime; closing the window releases idle preview."""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time
from urllib.request import urlopen


def remote_command(project, python):
    return ('cd "$HOME"/'+shlex.quote(project)+' && exec '+shlex.quote(python)+
            ' -m experiments.ppal.eyes.passive_viewer --port 8767 --idle-preview --exit-on-stdin-close')


def browser_command(profile, url):
    for name in ('chromium','chromium-browser','google-chrome','google-chrome-stable'):
        binary=shutil.which(name)
        if binary:
            return [binary, '--user-data-dir='+str(profile), '--no-first-run', '--disable-extensions', '--disable-background-mode', '--app='+url]
    binary=shutil.which('firefox')
    if binary:return [binary,'--no-remote','--profile',str(profile),'--new-window',url]
    raise RuntimeError('Install Firefox or Chromium to open Charlie Eyes')


def notify(message):
    try:
        import tkinter as tk
        from tkinter.messagebox import showerror
        root=tk.Tk();root.withdraw();showerror('Charlie Eyes',message);root.destroy()
    except Exception:
        subprocess.run(['notify-send','Charlie Eyes',message],check=False)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--host',default='five@charlie.local')
    ap.add_argument('--project',default='Projects/charlie',help='Pi repository path relative to its home')
    ap.add_argument('--python',default='.venv/bin/python')
    args=ap.parse_args()
    ssh=None;browser=None
    with tempfile.TemporaryDirectory(prefix='charlie-eyes-') as folder:
        folder=Path(folder)
        env=os.environ.copy()
        askpass=shutil.which('ssh-askpass') or '/usr/lib/openssh/gnome-ssh-askpass'
        if not Path(askpass).exists():
            helper=folder/'askpass'
            helper.write_text("#!/usr/bin/python3\nimport sys, tkinter as tk\nfrom tkinter.simpledialog import askstring\nroot=tk.Tk(); root.withdraw()\nprompt=sys.argv[1] if len(sys.argv)>1 else 'SSH authentication'\nsecret=any(word in prompt.lower() for word in ('password','passphrase'))\nanswer=askstring('Charlie SSH',prompt,show='*' if secret else None,parent=root)\nroot.destroy()\nif answer is None:sys.exit(1)\nprint(answer)\n")
            helper.chmod(0o700);askpass=str(helper)
        if Path(askpass).exists():
            env.update(SSH_ASKPASS=askpass,SSH_ASKPASS_REQUIRE='force')
        try:
            browser_args=browser_command(folder/'browser','http://127.0.0.1:8767')
            with (folder/'ssh.log').open('w+') as log:
                ssh=subprocess.Popen(['ssh','-T','-o','ExitOnForwardFailure=yes','-o','ConnectTimeout=10',
                    '-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2',
                    '-L','127.0.0.1:8767:127.0.0.1:8767',args.host,
                    remote_command(args.project,args.python)],stdin=subprocess.PIPE,
                    stdout=log,stderr=log,env=env,start_new_session=True)
                deadline=time.monotonic()+45
                while time.monotonic()<deadline:
                    if ssh.poll() is not None:
                        log.seek(0);raise RuntimeError('Could not start Charlie Eyes:\n'+log.read()[-3000:])
                    try:
                        with urlopen('http://127.0.0.1:8767/frame',timeout=.5) as response:
                            if response.status==200:break
                    except OSError:time.sleep(.1)
                else:raise RuntimeError('Connection timed out. Check SSH key/agent and the Pi hostname.')
                browser=subprocess.Popen(browser_args,stdout=subprocess.DEVNULL,stderr=log)
                while browser.poll() is None:
                    if ssh.poll() is not None:
                        raise RuntimeError('Charlie Eyes connection closed; reopen the launcher to reconnect')
                    time.sleep(.2)
        except Exception as exc:
            notify(str(exc))
        finally:
            if browser and browser.poll() is None:
                browser.terminate()
                try:browser.wait(timeout=3)
                except subprocess.TimeoutExpired:browser.kill();browser.wait()
            if ssh:
                if ssh.stdin:ssh.stdin.close()  # remote EOF shuts down server/camera
                try:ssh.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    ssh.terminate()
                    try:ssh.wait(timeout=3)
                    except subprocess.TimeoutExpired:ssh.kill();ssh.wait()


if __name__=='__main__':main()
