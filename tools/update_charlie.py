#!/usr/bin/env python3
"""
Charlie system updater.

Performs:

    • git pull
    • synchronize RP2040
    • restart Charlie service

Future versions will detect whether the RP2040 changed,
perform dependency updates, and run diagnostics.
"""

from __future__ import annotations

import subprocess
import sys

from tools.sync_rp2040 import Synchronizer


CHARLIE_SERVICE = "charlie"


class UpdateError(RuntimeError):
    pass


class CharlieUpdater:

    def run_command(self, *cmd: str) -> subprocess.CompletedProcess:

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise UpdateError(result.stderr.strip())

        return result

    def git_pull(self):

        print()
        print("Updating repository...")

        result = self.run_command(
            "git",
            "pull",
        )

        print(result.stdout.strip())

    def sync_rp2040(self):

        print()
        print("Synchronizing Raspberry Pi Pico...")

        Synchronizer().run()

    def restart_charlie(self):

        print()
        print("Restarting Charlie service...")

        self.run_command(
            "sudo",
            "systemctl",
            "restart",
            CHARLIE_SERVICE,
        )

        print("Charlie restarted.")

    def update(self):

        print("=" * 50)
        print("Charlie Updater")
        print("=" * 50)

        self.git_pull()

        self.sync_rp2040()

        self.restart_charlie()

        print()
        print("Update complete.")


def main():

    try:

        CharlieUpdater().update()

    except (UpdateError, RuntimeError) as exc:

        print()
        print(f"ERROR: {exc}")

        sys.exit(1)


if __name__ == "__main__":
    main()