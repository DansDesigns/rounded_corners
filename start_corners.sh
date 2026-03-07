#!/bin/bash
if [ ! -d "venv" ]; then
    python3 -m venv corner-venv
fi
source corner-venv/bin/activate
pip install pillow screeninfo
sudo apt install python3-tk
python3 rounded_corners.py "$@"
