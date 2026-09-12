#!/usr/bin/env python3
"""
Synchronize Charlie's RP2040 software with the
connected pico:ed.

Application Python files in rp2040/ are copied to
the Pico root.

Hardware/support libraries in rp2040/lib/ are copied
to /lib on the Pico.

The Pico is rebooted after synchronization.
"""

from pathlib import Path
import sys

from tools.mpremote_helper import (
    MpRemote,
    MpRemoteError,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

RP2040_DIR = (
    PROJECT_ROOT
    / "rp2040"
)

LIB_DIR = (
    RP2040_DIR
    / "lib"
)


class Synchronizer:

    def __init__(self):

        self.mp = MpRemote()

    # --------------------------------------------------

    def verify(self):

        print(
            "Checking environment..."
        )

        self.mp.require()

        if not RP2040_DIR.exists():

            raise RuntimeError(
                "Missing directory: "
                + str(RP2040_DIR)
            )

        if not self.mp.is_connected():

            raise RuntimeError(
                "No RP2040 running "
                "MicroPython was detected."
            )

    # --------------------------------------------------

    def _ensure_remote_directory(
        self,
        remote_path
    ):

        try:
            self.mp.mkdir(
                remote_path
            )

        except MpRemoteError:

            # Most commonly this means the
            # directory already exists.
            pass

    # --------------------------------------------------

    def synchronize_application(self):

        print()
        print(
            "Synchronizing RP2040 application..."
        )
        print()

        files = sorted(
            RP2040_DIR.glob("*.py")
        )

        if not files:

            raise RuntimeError(
                "No Python files found in: "
                + str(RP2040_DIR)
            )

        for source in files:

            destination = (
                ":" + source.name
            )

            print(
                "  Uploading "
                + source.name
                + "..."
            )

            self.mp.copy(
                source,
                destination
            )

    # --------------------------------------------------

    def synchronize_libraries(self):

        if not LIB_DIR.exists():
            return

        print()
        print(
            "Synchronizing RP2040 libraries..."
        )
        print()

        self._ensure_remote_directory(
            ":lib"
        )

        files = sorted(
            LIB_DIR.rglob("*.py")
        )

        for source in files:

            relative = source.relative_to(
                LIB_DIR
            )

            remote_parent = (
                relative.parent
            )

            if str(remote_parent) != ".":

                current = ":lib"

                for part in remote_parent.parts:

                    current += (
                        "/"
                        + part
                    )

                    self._ensure_remote_directory(
                        current
                    )

            destination = (
                ":lib/"
                + relative.as_posix()
            )

            print(
                "  Uploading lib/"
                + relative.as_posix()
                + "..."
            )

            self.mp.copy(
                source,
                destination
            )

    # --------------------------------------------------

    def synchronize(self):

        self.synchronize_application()
        self.synchronize_libraries()

        print()
        print(
            "Synchronization complete."
        )

    # --------------------------------------------------

    def reboot(self):

        print()
        print(
            "Restarting RP2040..."
        )

        self.mp.reset()

        print(
            "Restart complete."
        )

    # --------------------------------------------------

    def run(self):

        print(
            "=" * 40
        )

        print(
            "Charlie RP2040 Synchronizer"
        )

        print(
            "=" * 40
        )

        self.verify()
        self.synchronize()
        self.reboot()

        print()
        print(
            "Finished."
        )


def main():

    try:

        Synchronizer().run()

    except (
        RuntimeError,
        MpRemoteError,
    ) as exc:

        print()
        print(
            "ERROR: "
            + str(exc)
        )

        sys.exit(1)


if __name__ == "__main__":
    main()