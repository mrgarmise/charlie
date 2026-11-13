"""Offline ESP32-S3 app size/header gate; never opens a serial device."""
import hashlib
from pathlib import Path
import sys


def inspect(path):
    image=Path(path).read_bytes()
    if not 24 <= len(image) <= 0x330000:
        raise ValueError('application does not fit active slot')
    if image[0] != 0xe9 or int.from_bytes(image[12:14],'little') != 9:
        raise ValueError('ESP32-S3 application header required')
    return {'bytes':len(image),'sha256':hashlib.sha256(image).hexdigest(),
            'chip':'esp32s3','slot_bytes':0x330000}


if __name__ == '__main__':
    print(inspect(sys.argv[1]))
