# Universal Rounded Corners 
for ANY system that runs python 3.x

![](https://github.com/DansDesigns/rounded_corners/blob/main/corners.png)

Draws pure-black rounded-corner overlays on every connected monitor.
Always on top, variable arc radius - identical to the macOS corner effect.


Each corner tile is a solid black square with a quarter-circle cut out of
the inner-facing corner (the one pointing toward the screen centre).
![](https://github.com/DansDesigns/rounded_corners/blob/main/linux.png)

# To Install:

clone or download this repo & unzip.

on Windows:
```
run: start_corners.bat
```
on Linux:
```
open terminal
run: chmod +x install-corners.sh
run: ./install-corners.sh
```

Auto-Start:

Windows:
```
The first time you run start_corners.bat, it will automatically drop a shortcut into the Windows Startup folder.
Every subsequent login it will launch silently in the background.
```

Linux:
```
install-corners.sh installs to /usr/bin & adds an autostart in $HOME/.config/autostart, along with an icon.
```
