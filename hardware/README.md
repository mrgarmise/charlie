# Charlie Hardware Map

This file tracks hardware ownership and reserved interfaces.

## Raspberry Pi 5

Primary computer for Charlie.

### 40-pin GPIO header

GPIO17 / physical pin 11:
- RESERVED: Charlie Recovery Select
- Active LOW
- Ground to physical pin 9 during power-on to request recovery boot
- Do not reuse without redesigning the EEPROM recovery configuration

Physical pin 9:
- GND
- Used as the current recovery-select ground connection

All other Raspberry Pi GPIO header assignments are currently uncommitted.

Future hardware must be checked against this map before assigning GPIO pins.

### Dedicated interfaces

RP2040:
- Connected separately over USB
- Pi sends high-level motion/behavior commands
- RP2040 owns low-level servo execution

Camera:
- Raspberry Pi camera interface
- Does not currently consume GPIO17

Future NVMe:
- Expected to use the Raspberry Pi 5 PCIe interface
- Check HAT/control-pin requirements before installation

## Recovery USB

PNY 128 GB USB:

- p1 Ventoy
- p2 VTOYEFI
- p3 CHARLIEBOOT
- p4 CHARLIE_RESCUE

See `docs/recovery.md` for the complete recovery architecture.
