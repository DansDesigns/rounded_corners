#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install pillow screeninfo pygame python-xlib -q

# Create autostart entry if it doesn't exist yet
DESKTOP_FILE="$HOME/.config/autostart/rounded-corners.desktop"
SCRIPT_PATH="$(realpath "$0")"

if [ ! -f "$DESKTOP_FILE" ]; then
    mkdir -p "$HOME/.config/autostart"
    cat > "$DESKTOP_FILE" << DESKTOP
[Desktop Entry]
Type=Application
Name=Rounded Corners
Exec=/bin/bash $SCRIPT_PATH
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
DESKTOP
    echo "Autostart entry created at $DESKTOP_FILE"
fi

python3 rounded_corners.py "$@"
