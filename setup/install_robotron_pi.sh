#!/usr/bin/env bash
# Run as the normal Pi user. No game commands or services are started.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ ! -r /proc/device-tree/model ]] || ! grep -q 'Raspberry Pi 5' /proc/device-tree/model; then
  echo 'Run this installer on Charlie Raspberry Pi 5.' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y python3-venv python3-picamera2 python3-numpy python3-pil python3-opencv python3-matplotlib
python3 -m venv --system-site-packages .venv-robotron
.venv-robotron/bin/python -c 'import picamera2, numpy, PIL, cv2; print("Pi camera and vision dependencies OK")'
.venv-robotron/bin/python -m unittest discover -s tests -v
printf '\nReady. Activate with: source .venv-robotron/bin/activate\n'
