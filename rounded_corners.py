"""
rounded_corners.py
------------------
Draws pure-black rounded-corner overlays on every connected monitor.
Always on top, variable arc radius - identical to the macOS corner effect.

Windows : uses tkinter + transparentcolor (no extra deps beyond pillow/screeninfo)
Linux   : uses pygame + python-xlib shape extension for true per-pixel cutout

Requirements:
    pip install pillow screeninfo
    # Linux only:
    pip install pygame python-xlib

Usage:
    python rounded_corners.py            # default arc radius (30 px)
    python rounded_corners.py --arc 60   # custom arc radius
"""

import argparse
import sys
import platform
import os
import threading

IS_WINDOWS = platform.system() == "Windows"

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("ERROR: pip install pillow")
    sys.exit(1)

try:
    from screeninfo import get_monitors as _si_monitors
    def get_monitors():
        return [(m.x, m.y, m.width, m.height) for m in _si_monitors()]
except ImportError:
    def get_monitors():
        return None


# ======================= shared image builder =======================

def build_corner_rgba(arc, corner):
    """Return an RGBA PIL image: black corner shape, transparent cutout."""
    size = arc
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    cfg  = {
        "tl": ((size, size), 180, 270),
        "tr": ((0,    size), 270, 360),
        "bl": ((size, 0   ),  90, 180),
        "br": ((0,    0   ),   0,  90),
    }
    (cx, cy), start, end = cfg[corner]
    bbox = (cx - arc, cy - arc, cx + arc, cy + arc)
    draw.pieslice(bbox, start=start, end=end, fill=(0, 0, 0, 0))
    return img


# ══════════════════════════════════════════════════════════════════════════════
#  WINDOWS - tkinter + transparentcolor
# ══════════════════════════════════════════════════════════════════════════════

def run_windows(monitors, arc):
    import tkinter as tk
    from PIL import ImageTk

    TKEY     = "#010101"
    TKEY_RGB = (1, 1, 1)

    def make_photo(arc, corner):
        img   = build_corner_rgba(arc, corner)
        rgb   = img.convert("RGB")
        pix   = rgb.load()
        alpha = img.split()[3].load()
        for y in range(arc):
            for x in range(arc):
                if alpha[x, y] == 0:
                    pix[x, y] = TKEY_RGB
        return ImageTk.PhotoImage(rgb)

    root = tk.Tk()
    root.withdraw()

    all_wins = []

    for (mx, my, mw, mh) in monitors:
        print(f"  Monitor {mw}x{mh} @ ({mx},{my})")
        positions = {
            "tl": (mx,            my),
            "tr": (mx + mw - arc, my),
            "bl": (mx,            my + mh - arc),
            "br": (mx + mw - arc, my + mh - arc),
        }
        for key, (wx, wy) in positions.items():
            photo = make_photo(arc, key)
            win   = tk.Toplevel(root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.geometry(f"{arc}x{arc}+{wx}+{wy}")
            win.attributes("-transparentcolor", TKEY)
            win.configure(bg=TKEY)
            canvas = tk.Canvas(win, width=arc, height=arc,
                               bg=TKEY, highlightthickness=0)
            canvas.pack()
            canvas.create_image(0, 0, anchor="nw", image=photo)
            canvas._ref = photo
            all_wins.append(win)

    def pulse():
        for w in all_wins:
            try:
                w.attributes("-topmost", True)
                w.lift()
            except tk.TclError:
                pass
        root.after(500, pulse)

    pulse()

    try:
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)


# ══════════════════════════════════════════════════════════════════════════════
#  LINUX - one subprocess per corner (avoids pygame single-display limitation)
# ══════════════════════════════════════════════════════════════════════════════

LINUX_CORNER_CODE = """
import sys, os, time
arc    = int(sys.argv[1])
corner = sys.argv[2]
wx     = int(sys.argv[3])
wy     = int(sys.argv[4])

from PIL import Image, ImageDraw
import pygame
from Xlib import display as Xdisplay, X
from Xlib.ext import shape

def build_corner_rgba(arc, corner):
    size = arc
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    cfg  = {
        "tl": ((size, size), 180, 270),
        "tr": ((0,    size), 270, 360),
        "bl": ((size, 0   ),  90, 180),
        "br": ((0,    0   ),   0,  90),
    }
    (cx, cy), start, end = cfg[corner]
    bbox = (cx - arc, cy - arc, cx + arc, cy + arc)
    draw.pieslice(bbox, start=start, end=end, fill=(0, 0, 0, 0))
    return img

os.environ["SDL_VIDEO_WINDOW_POS"] = f"{wx},{wy}"

# ======================= Step 1: set all WM hints via Xlib BEFORE pygame maps the window =======================
# We open a direct Xlib connection and create+configure a window ourselves,
# then hand its ID to SDL via SDL_WINDOWID so pygame renders into it.
xdpy       = Xdisplay.Display()
screen_num = xdpy.get_default_screen()
xscreen    = xdpy.screen(screen_num)
root       = xscreen.root

# Create the X window manually so we control it before it is mapped
xwin = root.create_window(
    wx, wy, arc, arc, 0,
    xscreen.root_depth,
    X.InputOutput,
    X.CopyFromParent,
    background_pixel=xscreen.black_pixel,
    event_mask=X.ExposureMask | X.StructureNotifyMask,
    override_redirect=True,   # bypass WM completely — no decorations, no taskbar
)

# Set window type + state hints before mapping
ATOM = xdpy.intern_atom("ATOM")
xwin.change_property(xdpy.intern_atom("_NET_WM_WINDOW_TYPE"), ATOM, 32,
                     [xdpy.intern_atom("_NET_WM_WINDOW_TYPE_DOCK")])
xwin.change_property(xdpy.intern_atom("_NET_WM_STATE"), ATOM, 32, [
    xdpy.intern_atom("_NET_WM_STATE_ABOVE"),
    xdpy.intern_atom("_NET_WM_STATE_SKIP_TASKBAR"),
    xdpy.intern_atom("_NET_WM_STATE_SKIP_PAGER"),
])

# Map (show) the window now that hints are set
xwin.map()
xdpy.sync()

# ======================= Step 2: tell SDL to render into our pre-configured X window =======================
os.environ["SDL_WINDOWID"] = str(xwin.id)

pygame.init()
screen = pygame.display.set_mode((arc, arc), pygame.NOFRAME)
pygame.event.pump()
pygame.display.flip()
time.sleep(0.3)

img  = build_corner_rgba(arc, corner)
surf = pygame.image.fromstring(img.tobytes(), img.size, "RGBA").convert_alpha()

# ======================= Step 3: apply X11 shape mask to cut the arc =======================
alpha_px   = img.split()[3].load()
bitmap     = root.create_pixmap(arc, arc, 1)
gc         = bitmap.create_gc(foreground=0, background=0)
bitmap.fill_rectangle(gc, 0, 0, arc, arc)
gc.change(foreground=1)

for y in range(arc):
    for x in range(arc):
        if alpha_px[x, y] > 0:
            bitmap.fill_rectangle(gc, x, y, 1, 1)

xwin.shape_mask(shape.SO.Set, shape.SK.Bounding, 0, 0, bitmap)
gc.free()
xdpy.sync()

clock = pygame.time.Clock()
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit(0)
    screen.fill((0, 0, 0))
    screen.blit(surf, (0, 0))
    pygame.display.flip()
    clock.tick(30)
"""


def run_linux(monitors, arc):
    try:
        import pygame
        from Xlib import display as Xdisplay
        from Xlib.ext import shape
    except ImportError:
        print("ERROR: Linux requires:  pip install pygame python-xlib")
        sys.exit(1)

    import subprocess, tempfile

    # Write the corner worker script to a temp file
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
    tmp.write(LINUX_CORNER_CODE)
    tmp.close()

    procs = []
    for (mx, my, mw, mh) in monitors:
        print(f"  Monitor {mw}x{mh} @ ({mx},{my})")
        positions = {
            "tl": (mx,            my),
            "tr": (mx + mw - arc, my),
            "bl": (mx,            my + mh - arc),
            "br": (mx + mw - arc, my + mh - arc),
        }
        for corner, (wx, wy) in positions.items():
            p = subprocess.Popen(
                [sys.executable, tmp.name, str(arc), corner, str(wx), str(wy)]
            )
            procs.append(p)

    print("\nOverlays active. Ctrl-C to quit.")
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
        os.unlink(tmp.name)
        sys.exit(0)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Rounded-corner overlay for every connected monitor.")
    parser.add_argument("--arc", type=int, default=40,
                        help="Corner arc radius in pixels (default: 30)")
    args = parser.parse_args()
    arc  = max(5, args.arc)

    print(f"Rounded-corner overlay  |  arc = {arc} px  |  "
          f"{'Windows' if IS_WINDOWS else 'Linux'}")
    print("Ctrl-C to quit.\n")

    monitors = get_monitors()
    if not monitors:
        if IS_WINDOWS:
            import tkinter as tk
            root = tk.Tk(); root.withdraw()
            monitors = [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]
            root.destroy()
        else:
            import subprocess, re
            try:
                out = subprocess.check_output(["xrandr"]).decode()
                monitors = [(int(x),int(y),int(w),int(h))
                            for w,h,x,y in re.findall(r"(\d+)x(\d+)\+(\d+)\+(\d+)", out)]
            except Exception:
                monitors = [(0, 0, 1920, 1080)]

    if IS_WINDOWS:
        run_windows(monitors, arc)
    else:
        run_linux(monitors, arc)


if __name__ == "__main__":
    main()
