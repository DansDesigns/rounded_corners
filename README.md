# Universal Rounded Corners
for Linux & Windows


Draws pure-black rounded-corner overlays on every connected monitor.
Always on top, variable arc radius — identical to the macOS corner effect.


Each corner tile is a solid black square with a quarter-circle cut out of
the inner-facing corner (the one pointing toward the screen centre).


Usage:
```
python rounded_corners.py            # default arc radius (30 px)
python rounded_corners.py --arc 60   # custom arc radius
```
Auto-Start:

Windows:
```
The first time you run start_corners.bat, it will automatically drop a shortcut into the Windows Startup folder.
Every subsequent login it will launch silently in the background.
```

Linux — .desktop autostart entry:
```
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/rounded-corners.desktop << EOF
[Desktop Entry]
Type=Application
Name=Rounded Corners
Exec=/bin/bash /home/$USER/rounded_corners/start_corners.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
```
