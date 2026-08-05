"""
Wrapper around the official MicroPython mpremote CLI.

This module centralizes all interaction with mpremote so the rest of
the project never shells out directly.

Future tools (sync_rp2040.py, diagnostics.py, backup_pico.py, etc.)
should import this module instead of invoking subprocess themselves.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable


class MpRemoteError(RuntimeError):
    """Raised when mpremote returns an error."""


class MpRemote:
    """
    Thin wrapper around the official mpremote command line utility.
    """

    def __init__(self, executable: str = "mpremote"):
        self.executable = executable

    def installed(self) -> bool:
        """Return True if mpremote is available."""
        return shutil.which(self.executable) is not None

    def require(self) -> None:
        """Raise if mpremote is not installed."""
        if not self.installed():
            raise MpRemoteError(
                "mpremote is not installed.\n\n"
                "Install with:\n"
                "    python3 -m pip install --upgrade mpremote"
            )

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """
        Execute an mpremote command.

        Returns the CompletedProcess object.
        """

        cmd = [self.executable, *args]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if check and result.returncode != 0:
            raise MpRemoteError(result.stderr.strip())

        return result

    def version(self) -> str:
        """Return mpremote version string."""

        result = self.run("--version")

        return result.stdout.strip()

    def reset(self) -> None:
        """Soft reset the connected Pico."""

        self.run("reset")

    def copy(self, source: Path, destination: str) -> None:
        """
        Copy a file or directory to the Pico.

        Example:

            copy(Path("rp2040"), ":")
        """

        self.run(
            "fs",
            "cp",
            "-r",
            str(source),
            destination,
        )

    def remove(self, remote_path: str) -> None:
        """Delete a file on the Pico."""

        self.run(
            "fs",
            "rm",
            remote_path,
        )

    def mkdir(self, remote_path: str) -> None:
        """Create a directory on the Pico."""

        self.run(
            "fs",
            "mkdir",
            remote_path,
        )

    def list(self, remote_path: str = ":") -> str:
        """Return directory listing."""

        result = self.run(
            "fs",
            "ls",
            remote_path,
        )

        return result.stdout
        
    def is_connected(self) -> bool:
    """Return True if a Pico is reachable."""
    try:
        self.run("fs", "ls")
            return True
        except MpRemoteError:
            return False
            
    def exists(self, remote_path: str) -> bool:
    """
    Return True if a file exists on the Pico.
    """