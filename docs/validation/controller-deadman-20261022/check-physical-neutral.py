"""Read-only independent kernel check; never creates or grabs a controller."""
import argparse
import fcntl
import json
import os
import struct

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--event', required=True, help='operator-identified /dev/input/eventN')
args = parser.parse_args()
fd = os.open(args.event, os.O_RDONLY | os.O_NONBLOCK)
try:
    name = fcntl.ioctl(fd, 0x81004506, bytes(256)).split(b'\0', 1)[0].decode()
    if name != 'Charlie Virtual Controller':
        raise SystemExit('wrong device: ' + name)
    # EVIOCGABS: struct input_absinfo contains six signed 32-bit integers.
    axes = {str(axis): struct.unpack('6i', fcntl.ioctl(fd, 0x80184540 + axis, bytes(24)))[0]
            for axis in (0, 1, 2, 3, 4, 5, 16, 17)}
    keys = fcntl.ioctl(fd, 0x80604518, bytes(96))
    held_keys = [code for code in range(768) if keys[code // 8] & (1 << (code % 8))]
    neutral = not any(axes.values()) and not held_keys
    print(json.dumps(dict(device=args.event, name=name, axes=axes,
                          held_keys=held_keys, neutral=neutral), indent=2))
    raise SystemExit(0 if neutral else 1)
finally:
    os.close(fd)
