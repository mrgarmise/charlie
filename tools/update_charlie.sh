#!/bin/bash

set -e

echo
echo "Updating Charlie..."

git pull

python3 tools/sync_rp2040.py

sudo systemctl restart charlie

echo
echo "Charlie updated."