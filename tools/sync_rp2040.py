#!/usr/bin/env python3

"""
Synchronize Charlie's rp2040 directory to the connected Pico.

Requires:
    pip install mpremote
"""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "rp2040"


def run(cmd):
    print(" ".join(cmd))
    result = subprocess.run(cmd)

    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


def main():

    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)

    print("=====================================")
    print(" Charlie RP2040 Synchronizer")
    print("=====================================")

    files = sorted(SOURCE.glob("*.py"))

    if not files:
        print("No Python files found.")
        return

    for file in files:

        print(f"Uploading {file.name}")

        run([
            "mpremote",
            "fs",
            "cp",
            str(file),
            f":{file.name}"
        ])

    print()

    print("Restarting Pico...")

    run([
        "mpremote",
        "reset"
    ])

    print()
    print("Synchronization complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
        sys.exit(1)