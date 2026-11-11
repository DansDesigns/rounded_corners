#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "Installing Rounded Corners..."

# The app-menu and login autostart entries are per-user files. Running
# the complete installer with sudo would write those files to root's home.
if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
    echo "ERROR: Run install_corners.sh as the desktop user, not with sudo." >&2
    exit 1
fi

# On AlternixOS use the pattern/PIN authorisation wrapper; retain standard
# sudo for other Linux distributions that do not provide osm-sudo.
if command -v osm-sudo >/dev/null 2>&1; then
    elevate() { osm-sudo "$@"; }
else
    elevate() { sudo "$@"; }
fi

# tkinter powers the settings window. The overlay itself needs no tkinter.
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
    elevate apt-get install -y python3-tk
fi

# Existing overlay dependencies.
elevate pip3 install pillow screeninfo python-xlib --break-system-packages

# Update the actual app, not a separate patch/fix script.
elevate install -m 755 rounded_corners.py /usr/bin/rounded_corners

if [ -f "corners.png" ]; then
    elevate mkdir -p /usr/share/icons/hicolor/64x64/apps
    elevate cp corners.png /usr/share/icons/hicolor/64x64/apps/corners.png
fi

# Examine the existing autostart entry before changing it. In older installs
# ~/.config/autostart may itself be a file: the Python installer recognises
# that legacy Rounded Corners entry and safely migrates it, leaving other
# applications' files untouched. Existing correct entries are not rewritten.
# Settings remain in the actual desktop user's home directory.
python3 /usr/bin/rounded_corners --install-shortcuts

# Show corners immediately as well as on future logins, if enabled.
python3 /usr/bin/rounded_corners --overlay >/dev/null 2>&1 </dev/null &

echo "Installed. Open 'Rounded Corners' from your app launcher to configure."
