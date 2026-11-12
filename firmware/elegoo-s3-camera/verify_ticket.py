"""Explicitly confirm a browser transaction using reviewed Charlie PR #28 peer.

Run with PYTHONPATH pointing to the reviewed Pi peer checkout. No NetworkManager,
Wi-Fi switch, camera, serial or actuator import is made. Discovery is a hint only;
TLSProtocol's locally enrolled certificate pin and token remain authoritative.
"""
import argparse
import json
from pathlib import Path
import re
import time


def parse_ticket(raw,expected_device):
    if len(raw.encode())>1024:raise ValueError('ticket exceeds bound')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('duplicate field')
            result[key]=value
        return result
    ticket=json.loads(raw,object_pairs_hook=unique)
    if not isinstance(ticket,dict) or set(ticket)!={'version','device_id','transaction','ssid','lease_seconds'}:
        raise ValueError('ticket schema rejected')
    if (type(ticket['version']) is not int or ticket['version']!=1
            or ticket['device_id']!=expected_device or not re.fullmatch(r'elegoo-[a-f0-9]{12}',expected_device)
            or not isinstance(ticket['transaction'],str) or not re.fullmatch(r'[a-f0-9]{32}',ticket['transaction'])
            or not isinstance(ticket['ssid'],str) or not 1<=len(ticket['ssid'].encode())<=32 or '\0' in ticket['ssid']
            or type(ticket['lease_seconds']) is not int or not 1<=ticket['lease_seconds']<=90):
        raise ValueError('ticket identity or bounds rejected')
    return ticket


def verify(ticket,protocol,discovery,*,clock=time.monotonic,sleep=time.sleep):
    deadline=clock()+min(ticket['lease_seconds'],90)
    while clock()<deadline:
        for endpoint in discovery.candidates(ticket['device_id'],deadline)[:8]:
            if clock()>=deadline:break
            try:
                status=protocol.status(endpoint,ticket['device_id'],deadline)
                if (status.get('device_id')!=ticket['device_id'] or status.get('joined') is not True
                        or status.get('transaction')!=ticket['transaction']):continue
                protocol.confirm(endpoint,ticket['device_id'],ticket['transaction'],ticket['ssid'],deadline)
                if clock()>=deadline:raise TimeoutError('confirmation deadline exceeded')
                return dict(verified=True,device_id=ticket['device_id'],transaction=ticket['transaction'])
            except (OSError,ValueError,TimeoutError):continue
        sleep(min(.5,max(0,deadline-clock())))
    raise TimeoutError('target LAN confirmation unverified; device recovery lease retained')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ticket',required=True);parser.add_argument('--enrollments',required=True)
    parser.add_argument('--lan-ip',required=True);parser.add_argument('--device-id',required=True)
    parser.add_argument('--hint',action='append',default=[])
    parser.add_argument('--authorize-confirm',action='store_true')
    args=parser.parse_args()
    if not args.authorize_confirm:parser.error('separate explicit --authorize-confirm is required')
    with Path(args.ticket).open('rb') as stream:raw=stream.read(1025)
    ticket=parse_ticket(raw.decode('utf-8'),args.device_id)
    # Native dependencies and all network activity occur AFTER explicit authorization.
    from networking.transport import SecretStore,TLSProtocol,Discovery,Endpoint
    from zeroconf import Zeroconf
    store=SecretStore(args.enrollments);store.load(args.device_id)
    with Zeroconf(interfaces=[args.lan_ip]) as zeroconf:
        discovery=Discovery(zeroconf,args.lan_ip,hints=[Endpoint(h) for h in args.hint])
        print(json.dumps(verify(ticket,TLSProtocol(store),discovery)))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,TimeoutError,ImportError):raise SystemExit('Verification unavailable or rejected; no network switch or motor operation performed') from None
