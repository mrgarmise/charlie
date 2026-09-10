# Charlie Recovery System

Charlie has a hardware-selected recovery environment that is independent of
the normal Raspberry Pi OS installation.

The recovery environment is stored on the same 128 GB PNY USB drive used as
the Ventoy rescue library.

## Proven recovery architecture

Normal Charlie:

    Raspberry Pi 5 EEPROM
            |
            | GPIO17 open
            v
       normal boot order
            |
            v
       microSD bootfs
            |
            v
       microSD rootfs

Recovery Charlie:

    Raspberry Pi 5 EEPROM
            |
            | GPIO17 grounded
            v
       PARTITION=3
            |
            v
       USB partition 3
       CHARLIEBOOT
            |
            v
       USB partition 4
       CHARLIE_RESCUE

This configuration has been tested successfully on the Raspberry Pi 5.

## Recovery selector hardware

Recovery select is active LOW.

- GPIO: GPIO17
- Physical header pin: 11
- Ground: physical header pin 9
- Temporary control: female-to-female Dupont jumper between pins 11 and 9

Jumper removed:
normal boot behavior.

Jumper installed before power-on:
EEPROM selects partition 3 for recovery.

GPIO17 / physical pin 11 is RESERVED for Charlie recovery and must not be
assigned to another peripheral without redesigning the recovery mechanism.

Power Charlie off before installing or removing the jumper.

## EEPROM configuration

Production configuration:

    [all]
    BOOT_UART=1
    BOOT_ORDER=0xf461
    NET_INSTALL_AT_POWER_ON=1
    PARTITION_WALK=1
    NETCONSOLE=6665@192.168.50.2/,6666@/
    XHCI_DEBUG=0x3

    [gpio17=0]
    PARTITION=3

    [all]

BOOT_ORDER 0xf461 currently provides the normal SD/NVMe/USB search behavior.

The conditional PARTITION=3 setting is deliberately used instead of a global
PARTITION=3 setting so Charlie's conventional two-partition SD installation
continues to boot normally when the recovery jumper is absent.

## Recovery USB layout

The PNY 128 GB USB currently uses an MBR partition table:

    Partition 1
      Label: Ventoy
      Filesystem: exFAT
      Size: approximately 103.4 GB
      PARTUUID: 7587e895-01

    Partition 2
      Label: VTOYEFI
      Filesystem: FAT
      Size: 32 MB
      PARTUUID: 7587e895-02

    Partition 3
      Label: CHARLIEBOOT
      Filesystem: FAT32
      Size: 512 MB
      PARTUUID: 7587e895-03
      Rescue mount: /boot/firmware

    Partition 4
      Label: CHARLIE_RESCUE
      Filesystem: ext4
      Size: approximately 11.5 GB
      PARTUUID: 7587e895-04
      Rescue mount: /

Ventoy retains partitions 1 and 2. Charlie's native Raspberry Pi recovery OS
occupies partitions 3 and 4.

## Rescue operating system

Verified rescue identity:

    hostname: charlie-rescue
    user: five
    UID/GID: 1000/1000
    home: /home/five
    architecture: aarch64 / arm64
    OS: Debian 13 / Raspberry Pi OS-derived Trixie image

The rescue root filesystem is /dev/sda4.

The rescue boot filesystem is /dev/sda3.

SSH is enabled.

Useful verification command:

    charlie-rescue-check

Expected key output:

    five
    charlie-rescue
    64
    arm64

and:

    /               -> /dev/sda4
    /boot/firmware  -> /dev/sda3

## Normal recovery procedure

1. Shut Charlie down completely.
2. Remove the normal microSD card if recovering from SD failure.
3. Insert the Charlie/Ventoy recovery USB.
4. Connect GPIO17 physical pin 11 to GND physical pin 9.
5. Connect Ethernet if network access is required.
6. Power Charlie on.
7. Connect with:

       ssh five@charlie-rescue.local

8. Verify with:

       charlie-rescue-check

9. Perform the required repair, restore, imaging, or diagnostics.
10. Shut rescue Charlie down cleanly:

       sudo poweroff

11. Remove the GPIO17-to-GND recovery jumper.
12. Restore/install normal boot storage.
13. Power Charlie on normally.

Never leave the recovery jumper installed when expecting ordinary boot
behavior.

## Early-boot diagnostics

Charlie retains EEPROM NETCONSOLE diagnostics because Charlie is normally
headless.

For direct boot diagnostics, connect Charlie Ethernet directly to MintHP.

MintHP Ethernet interface:

    enp1s0

A known diagnostic configuration on Mint is:

    192.168.50.1/24

Charlie EEPROM NETCONSOLE is configured as:

    NETCONSOLE=6665@192.168.50.2/,6666@/

Listen from Mint with:

    sudo tcpdump -ni enp1s0 udp port 6666 -A

For a saved log:

    sudo tcpdump -ni enp1s0 udp port 6666 -A | tee ~/charlie-boot.log

XHCI_DEBUG=0x3 provides useful USB mass-storage boot diagnostics.

This diagnostic path operates in the EEPROM bootloader before Linux, SSH,
or the normal filesystems need to work.

## Why explicit recovery partition selection is required

During development, Pi 5 EEPROM USB diagnostics showed that the PNY device
was detected correctly and all four MBR partitions were read correctly:

    p1 Ventoy
    p2 VTOYEFI
    p3 CHARLIEBOOT
    p4 CHARLIE_RESCUE

However, the default USB boot selection repeatedly resolved to partition 1.
PARTITION_WALK=1 did not successfully reach the Raspberry Pi boot filesystem
behind the Ventoy partitions.

Adding the GPIO17 conditional:

    [gpio17=0]
    PARTITION=3

caused the Pi 5 to boot CHARLIEBOOT successfully. Linux then mounted
CHARLIE_RESCUE as its root filesystem, Ethernet initialized, and SSH access
to five@charlie-rescue succeeded.

## Important recovery principle

The recovery USB is not merely a collection of backup files. It is a
self-contained ARM64 Raspberry Pi operating system capable of running even
when Charlie's primary operating system is unavailable.

Future recovery tooling should preserve this property.

Planned improvements include:

- Wi-Fi access in the rescue OS
- automated Charlie backup capture
- automated restore to SD/SSD
- integrity verification
- recovery menu / status command
- storage-device safety checks before destructive operations

## Network identities and Wi-Fi recovery

Charlie uses stable mDNS hostnames rather than depending on DHCP addresses:

    Normal Charlie:  charlie.local
    Rescue Charlie:  charlie-rescue.local

The router may assign different or reused IP addresses to Ethernet and Wi-Fi.
These addresses should not be treated as Charlie's identity.

The rescue OS has been tested successfully with Wi-Fi as its only network
connection. Its NetworkManager Wi-Fi profile reconnects automatically after
a cold boot, and Avahi advertises `charlie-rescue.local` over Wi-Fi.

Normal rescue access therefore requires only:

1. Power Charlie off.
2. Remove the normal SD card if appropriate for the recovery operation.
3. Insert the recovery USB.
4. Ground GPIO17 (physical pin 11) to GND (physical pin 9).
5. Power Charlie on.
6. From MintHP:

       ssh charlie-rescue

Ethernet is not normally required.

Ethernet remains an important fallback for:
- SSH when Wi-Fi is unavailable
- network troubleshooting
- direct MintHP-to-Charlie EEPROM NETCONSOLE diagnostics before Linux boots

### MintHP SSH aliases

MintHP may use the following `~/.ssh/config` entries:

    Host charlie
        HostName charlie.local
        User five

    Host charlie-rescue
        HostName charlie-rescue.local
        User five

This allows:

    ssh charlie

for the normal system and:

    ssh charlie-rescue

for the recovery system.

SSH host identity should normally be associated with these stable hostnames,
not temporary DHCP addresses.
