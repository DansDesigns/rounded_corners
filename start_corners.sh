#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
sudo pip3 install pillow screeninfo pygame python-xlib --break-system-packages

sudo cp rounded_corners.py /usr/bin/rounded_corners
sudo cp start_corners.sh /usr/bin/rounded_corners_start
sudo chmod +x /usr/bin/rounded_corners
sudo chmod +x /usr/bin/rounded_corners_start

sudo cp corners.png /usr/share/icons/hicolor/64x64/apps/corners.png

