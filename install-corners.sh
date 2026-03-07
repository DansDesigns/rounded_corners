#!/bin/bash
cd "$(dirname "$0")"

echo "Installing Rounded Corners..."

# Install dependencies system-wide
sudo pip3 install pillow screeninfo pygame python-xlib --break-system-packages

# Copy script to /usr/bin and make executable
sudo cp rounded_corners.py /usr/bin/rounded_corners
sudo chmod +x /usr/bin/rounded_corners

# Copy icon if it doesnt exist
if [ -f "corners.png" ]; then
    sudo mkdir -p /usr/share/icons/hicolor/64x64/apps
    sudo cp corners.png /usr/share/icons/hicolor/64x64/apps/corners.png
fi

# Create .desktop entry
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/rounded_corners.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Rounded Corners
Comment=Rounded corner overlay for all monitors
Exec=python3 /usr/bin/rounded_corners
Icon=corners
Terminal=false
Categories=Utility;
StartupNotify=false
EOF

cp $HOME/.local/share/applications/rounded_corners.desktop $HOME/.config/autostart
echo "Done! You can now launch rounded-corners from the terminal with:"
echo "python3 /usr/bin/rounded_corners,"
echo "use the application launcher entry,"
echo "Restart to test auto launch"
echo "or if running qtile, add to qtile autostart config with: subprocess.Popen(['python3', '/usr/bin/rounded_corners'])"