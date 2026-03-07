# Universal Rounded Corners
for Linux & Windows


Draws pure-black rounded-corner overlays on every connected monitor.
Always on top, variable arc radius — identical to the macOS corner effect.


Each corner tile is a solid black square with a quarter-circle cut out of
the inner-facing corner (the one pointing toward the screen centre).


Requirements:
```
pip install pillow screeninfo
```


Usage:
```
python rounded_corners.py            # default arc radius (30 px)
python rounded_corners.py --arc 60   # custom arc radius
```
