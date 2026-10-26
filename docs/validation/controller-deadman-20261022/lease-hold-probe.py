"""Operator-only controller diagnostic. Never invoke while a game is running.

Run from the ordinary Charlie terminal. After observing maintained holds, STOP
this PID from another terminal to verify independent server release. Resume and
Ctrl-C to clean up. This intentionally has no independent renewal thread.
"""
import argparse
import os
import socket
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--host', required=True)
parser.add_argument('--confirm-no-gameplay', action='store_true', required=True)
args = parser.parse_args()
with socket.create_connection((args.host, 8765), timeout=2) as connection:
    with connection.makefile('rwb', buffering=0) as stream:
        def command(token):
            stream.write(token.encode('ascii') + b'\n')
            if stream.readline(64) != b'OK\n':
                raise RuntimeError('rejected ' + token + '; reconnect after expiration')
        try:
            command('NEUTRAL')
            command('LEASE')
            for token in ('LS_RIGHT', 'RS_UP', 'DPAD_LEFT', 'A_DOWN', 'LT_DOWN'):
                command(token)
            print('Diagnostic holds active. Client PID:', os.getpid(), flush=True)
            while True:
                command('LEASE')
                time.sleep(.2)
        finally:
            command('NEUTRAL')
