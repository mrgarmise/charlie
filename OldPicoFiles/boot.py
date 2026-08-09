"""
boot.py

Executed every time the Pico boots.

Currently we simply allow the filesystem to mount
normally and then hand control to main.py.
"""

import gc

gc.enable()

print()
print("========================================")
print(" Cyberdeck Pico Agent Booting")
print("========================================")
print()

print("Memory:", gc.mem_free(), "bytes free")
