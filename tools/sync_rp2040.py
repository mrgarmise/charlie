#!/usr/bin/env python3
"""
Synchronize the Charlie RP2040 source tree with the connected Raspberry Pi Pico.

This tool uploads the contents of the repository's rp2040/ directory
to the Pico using the official MicroPython mpremote utility.

The script is intentionally independent of Charlie's runtime.
It may be run manually or by update_charlie.py.
"""

from pathlib import Path
import sys

from tools.mpremote_helper import MpRemote, MpRemoteError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RP2040_DIR = PROJECT_ROOT / "rp2040"


class Synchronizer:

    def __init__(self):

        self.mp = MpRemote()

    def verify(self):

        print("Checking environment...")

        self.mp.require()

        if not RP2040_DIR.exists():
            raise RuntimeError(f"Missing directory: {RP2040_DIR}")

        if not self.mp.is_connected():
            raise RuntimeError("No RP2040 running MicroPython was detected.")

    def synchronize(self):
        print()
        print("Synchronizing RP2040...")
        print()
        files = sorted(RP2040_DIR.glob("*.py"))
        if not files:
            raise RuntimeError(f"No Python files found in: {RP2040_DIR}")
        for source in files:
            destination = f":{source.name}"
            print(f"  Uploading {source.name}...")
            self.mp.copy(source, destination)
        print()
        print("Synchronization complete.")
        
    def reboot(self):

        print()
        print("Restarting RP2040...")

        self.mp.reset()

        print("Restart complete.")

    def run(self):

        print("=" * 40)
        print("Charlie RP2040 Synchronizer")
        print("=" * 40)

        self.verify()

        self.synchronize()

        self.reboot()

        print()
        print("Finished.")


def main():

    try:

        Synchronizer().run()

    except (RuntimeError, MpRemoteError) as exc:

        print()
        print(f"ERROR: {exc}")

        sys.exit(1)


if __name__ == "__main__":
    main()