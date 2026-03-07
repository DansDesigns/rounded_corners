#!/bin/bash
if [ ! -d "venv" ]; then
    python3 -m venv corner-venv
fi
source corner-venv/bin/activate
pip install pillow screeninfo tkinter
python3 rounded_corners.py "$@"
