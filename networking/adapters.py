"""Explicit saved-profile NetworkManager adapter; never invoked by monitoring.

Uses system D-Bus (python3-dbus OS package), with finite call timeouts. No shell,
password argv, profile creation, service restart or global routing mutation.
A daemon checkpoint survives client death. Rollback errors retain that checkpoint.
"""
from dataclasses import dataclass
import time
import json

from networking.transport import Endpoint


@dataclass(frozen=True)
class Checkpoint:
    path: str
    device: str
    saved: str
    snapshot: str


class DBusBackend:
    interface = 'org.freedesktop.NetworkManager'
    root = '/org/freedesktop/NetworkManager'

    def __init__(self):
        import dbus
        self.dbus = dbus
        self.bus = dbus.SystemBus()

    def call(self, path, interface, method, *args):
        proxy = self.bus.get_object(self.interface, path, introspect=False)
        try:
            return getattr(self.dbus.Interface(proxy, interface), method)(*args, timeout=3)
        except self.dbus.DBusException:
            raise OSError('NetworkManager operation failed') from None

    def manager(self, method, *args):
        return self.call(self.root, self.interface, method, *args)

    def property(self, path, interface, name):
        return self.call(path, 'org.freedesktop.DBus.Properties', 'Get', interface, name)

    def device(self, name):
        return str(self.manager('GetDeviceByIpIface', name))

    def saved(self, device):
        active = self.property(device, self.interface+'.Device', 'ActiveConnection')
        if str(active) == '/': return '/'
        return str(self.property(active, self.interface+'.Connection.Active', 'Connection'))

    def snapshot(self, device):
        result = {}
        for family in ('Ip4Config', 'Ip6Config'):
            path = self.property(device, self.interface+'.Device', family)
            if str(path) == '/':
                result[family] = None
            else:
                interface = self.interface+'.'+family.replace('Ip', 'IP')
                result[family] = {name: self.property(path, interface, name)
                                 for name in ('AddressData', 'RouteData', 'Nameservers')}
        return json.dumps(result, sort_keys=True, default=list)

    def checkpoint(self, device, seconds):
        # flags=0: refuse overlapping checkpoints; preserve others' checkpoints.
        return str(self.manager('CheckpointCreate', self.dbus.Array([device], signature='o'),
                                self.dbus.UInt32(seconds), self.dbus.UInt32(0)))

    def profile(self, uuid):
        return str(self.call(self.root+'/Settings', self.interface+'.Settings', 'GetConnectionByUuid', uuid))

    def validate_setup(self, profile, adapter):
        settings = self.call(profile, self.interface+'.Settings.Connection', 'GetSettings')
        connection = settings.get('connection', {})
        if (connection.get('type') != '802-11-wireless'
                or connection.get('interface-name') != adapter
                or any(settings.get(family, {}).get('never-default') is not True
                       and settings.get(family, {}).get('never-default') != 1
                       for family in ('ipv4', 'ipv6'))):
            raise ValueError('setup profile must bind adapter and forbid default routes')
        # Reject all explicit routes/DNS to protect the primary routing environment.
        for family in ('ipv4', 'ipv6'):
            block = settings.get(family, {})
            if any(block.get(key) for key in ('routes', 'route-data', 'routing-rules', 'dns', 'dns-data')):
                raise ValueError('setup profile may not install explicit routing or DNS')
            if not block.get('ignore-auto-routes', False):
                raise ValueError('setup profile must ignore DHCP routes')
            if not block.get('ignore-auto-dns', False):
                raise ValueError('setup profile must ignore DHCP DNS')

    def activate(self, profile, device):
        self.manager('ActivateConnection', self.dbus.ObjectPath(profile),
                     self.dbus.ObjectPath(device), self.dbus.ObjectPath('/'))

    def rollback(self, checkpoint):
        result = self.manager('CheckpointRollback', self.dbus.ObjectPath(checkpoint))
        return bool(result) and all(int(v) == 0 for v in result.values())

    def restored(self, device, saved):
        if saved == '/': return self.saved(device) == '/'
        return (self.saved(device) == saved and
                int(self.property(device, self.interface+'.Device', 'State')) == 100)

    def destroy(self, checkpoint):
        self.manager('CheckpointDestroy', self.dbus.ObjectPath(checkpoint))


class SavedAdapters:
    def __init__(self, backend, profiles, setup_endpoint, *, primary='wlan0', secondary=('wlan1',),
                 clock=time.monotonic, sleep=time.sleep):
        if primary in secondary: raise ValueError('primary cannot be a secondary adapter')
        self.backend, self.profiles, self.endpoint = backend, dict(profiles), setup_endpoint
        self.primary_name, self.secondary_names = primary, tuple(secondary)
        self.clock, self.sleep = clock, sleep

    def secondary(self):
        return self.secondary_names

    def primary(self):
        return self.primary_name

    def checkpoint(self, adapter, seconds):
        profile = self.backend.profile(self.profiles[adapter])
        self.backend.validate_setup(profile, adapter)
        device = self.backend.device(adapter)
        saved = self.backend.saved(device)
        snapshot = self.backend.snapshot(device)
        path = self.backend.checkpoint(device, seconds)
        return Checkpoint(path, device, saved, snapshot)

    def connect_setup(self, adapter, deadline):
        profile = self.backend.profile(self.profiles[adapter])
        device = self.backend.device(adapter)
        self.backend.validate_setup(profile, adapter)
        self.backend.activate(profile, device)
        while self.clock() < deadline:
            if self.backend.restored(device, profile): return self.endpoint
            self.sleep(min(.25, max(0, deadline-self.clock())))
        raise TimeoutError('setup association timed out')

    def restore(self, checkpoint, deadline):
        if not self.backend.rollback(checkpoint.path): return False
        while self.clock() < deadline:
            if (self.backend.restored(checkpoint.device, checkpoint.saved)
                    and self.backend.snapshot(checkpoint.device) == checkpoint.snapshot):
                # NM rollback normally destroys the checkpoint itself. No explicit
                # destruction here: never cancel daemon recovery before verification.
                return True
            self.sleep(min(.25, max(0, deadline-self.clock())))
        return False
