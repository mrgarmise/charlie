# Cyberdeck
A portable raspi5 AI cam tool

## Goals
- portable battery powered
- AI camera integration
- Computer Vision
- Mechanical Eye
- ChatGPT integration (possible voice)
- Robotics platform

## Current hardware
- Raspberry Pi 5
- Elecfreaks pico:ed (RP2040)
- Keyestudio micro:bit Sensor Shield V2
- Four SG90 servos
- Two pan/tilt mechanisms
- micro SD card for 32bit OS Trixie

## Current Software

- Python 3
- Event-driven behavior architecture
- Stimulus bus
- Attention manager
- Idle behavior
- Scan behavior
- RP2040 servo controller

## Project Structure

```
Cyberdeck/
??? attention/
??? behaviors/
??? motion/
??? stimulus/
??? main.py
```

## Project Vision

The robot should eventually:

- Maintain lifelike idle motion
- React to events
- Track objects and people
- Integrate Raspberry Pi AI Camera
- Learn increasingly sophisticated behaviors

The design emphasizes modularity so that sensors, AI models, and behaviors can evolve independently.


## Milestones
[X] Git
[X] Python virtual environment
[X] SSH keys
[X] VNC
[ ] 64bit OS
[ ] AI Camera
[ ] Open CV


## Notes
Do not install python modules globally. 
Use this command to install into virtual environment:

source ~/Projects/Cyberdeck/.venv/bin/activate

using github only

## Recovery System

Charlie now has a tested hardware-selected ARM64 rescue environment.

- Recovery selector: GPIO17 / physical pin 11 to GND / physical pin 9
- Rescue USB: shared PNY Ventoy/Charlie recovery drive
- Rescue hostname: `charlie-rescue`
- Rescue user: `five`
- EEPROM NETCONSOLE retained for headless early-boot diagnostics

See [`docs/recovery.md`](docs/recovery.md) for the recovery procedure and
[`hardware/README.md`](hardware/README.md) for reserved GPIO assignments.
