"""
rounded_corners.py
------------------
Draws pure-black rounded-corner overlays on every connected monitor.
Always on top, variable arc radius — identical to the macOS corner effect.

Each corner tile is a solid black square with a quarter-circle cut out of
the inner-facing corner (the one pointing toward the screen centre).

Requirements:
    pip install pillow screeninfo

Usage:
    python rounded_corners.py            # default arc radius (30 px)
    python rounded_corners.py --arc 60   # custom arc radius
"""

import tkinter as tk
import argparse
import sys

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    print("ERROR: Pillow is required.  Run:  pip install pillow")
    sys.exit(1)

try:
    from screeninfo import get_monitors as _si_monitors
    def get_monitors():
        return [(m.x, m.y, m.width, m.height) for m in _si_monitors()]
except ImportError:
    print("[warning] screeninfo not found – pip install screeninfo")
    print("          Falling back to tkinter single-monitor detection.\n")
    def get_monitors():
        return None


def get_monitors_fallback(root):
    return [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]


# Transparency key colour — virtually black, used so tkinter can mask it out.
TKEY = "#010101"
TKEY_RGB = (1, 1, 1)


def build_corner_image(arc: int, corner: str):
    """
    Returns a PhotoImage of size (arc x arc).

    The screen edge sits at one corner of the tile; the circle is centred
    exactly there with radius = arc.  We cut the quarter-pie that faces the
    interior of the screen, leaving a solid black L-shape whose inner edge
    follows a perfect arc.

        tl -> screen edge at (0,    0   )  cut: 0-90 deg
        tr -> screen edge at (size, 0   )  cut: 90-180 deg
        bl -> screen edge at (0,    size)  cut: 270-360 deg
        br -> screen edge at (size, size)  cut: 180-270 deg
    """
    size = arc
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    cfg = {
        "tl": ((size, size), 180, 270),
        "tr": ((0,    size), 270, 360),
        "bl": ((size, 0   ),  90, 180),
        "br": ((0,    0   ),   0,  90),
    }
    (cx, cy), start, end = cfg[corner]
    bbox = (cx - arc, cy - arc, cx + arc, cy + arc)
    draw.pieslice(bbox, start=start, end=end, fill=(0, 0, 0, 0))

    # Replace transparent pixels with key colour so tkinter can mask them
    rgb   = img.convert("RGB")
    pix   = rgb.load()
    alpha = img.split()[3].load()
    for y in range(size):
        for x in range(size):
            if alpha[x, y] == 0:
                pix[x, y] = TKEY_RGB

    return ImageTk.PhotoImage(rgb)


class MonitorCorners:
    """Creates four always-on-top corner windows for one monitor."""

    def __init__(self, root, mx, my, mw, mh, arc):
        self.root = root
        self.wins = []

        positions = {
            "tl": (mx,            my),
            "tr": (mx + mw - arc, my),
            "bl": (mx,            my + mh - arc),
            "br": (mx + mw - arc, my + mh - arc),
        }

        for key, (wx, wy) in positions.items():
            photo = build_corner_image(arc, key)

            win = tk.Toplevel(root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.geometry(f"{arc}x{arc}+{wx}+{wy}")
            win.attributes("-transparentcolor", TKEY)
            win.configure(bg=TKEY)

            canvas = tk.Canvas(win, width=arc, height=arc,
                               bg=TKEY, highlightthickness=0)
            canvas.pack()
            canvas.create_image(0, 0, anchor="nw", image=photo)
            canvas._ref = photo  # prevent garbage collection

            self.wins.append(win)

        self._pulse()

    def _pulse(self):
        for win in self.wins:
            try:
                win.attributes("-topmost", True)
                win.lift()
            except tk.TclError:
                return
        self.root.after(500, self._pulse)


def main():
    parser = argparse.ArgumentParser(
        description="Rounded-corner overlay for every connected monitor.")
    parser.add_argument("--arc", type=int, default=30,
                        help="Corner arc radius in pixels (default: 30)")
    args = parser.parse_args()
    arc = max(5, args.arc)

    print(f"Rounded-corner overlay  |  arc = {arc} px")
    print("Close this terminal (or Ctrl-C) to quit.\n")

    root = tk.Tk()
    root.withdraw()

    monitors = get_monitors()
    if not monitors:
        monitors = get_monitors_fallback(root)

    for (mx, my, mw, mh) in monitors:
        print(f"  Monitor {mw}x{mh}  offset ({mx},{my})")
        MonitorCorners(root, mx, my, mw, mh, arc)

    print("\nOverlays active.")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()