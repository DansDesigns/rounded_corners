"""
rounded_corners.py
------------------
Draws pure-black rounded-corner overlays on every connected monitor.
Always on top, variable arc radius - identical to the macOS corner effect.

Windows : uses tkinter + transparentcolor (no extra deps beyond pillow/screeninfo)
Linux   : uses raw Xlib + the X SHAPE extension, in a single lightweight process.
          No pygame/SDL2 - the corners are static and never redrawn, so a full
          game-loop library was never actually needed here.

Requirements:
    pip install pillow screeninfo
    # Linux only:
    pip install python-xlib

Usage:
    python rounded_corners.py            # default arc radius (40 px)
    python rounded_corners.py --arc 60   # custom arc radius
"""

import argparse
import sys
import platform
import os
import signal
import time

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
#  (unchanged: this path was already a single, light process)
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
        root.after(2000, pulse)  # 2s is plenty for re-asserting topmost

    pulse()

    try:
        root.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)


# ══════════════════════════════════════════════════════════════════════════════
#  LINUX - single process, raw Xlib + SHAPE extension, no pygame/SDL2
# ══════════════════════════════════════════════════════════════════════════════

def _build_shape_mask(root, arc, corner):
    """Build a 1-bit X pixmap mask (the SHAPE extension's bounding mask) from
    the PIL alpha channel for one corner. Built once, reused for every monitor."""
    img   = build_corner_rgba(arc, corner)
    alpha = img.split()[3].load()

    bitmap = root.create_pixmap(arc, arc, 1)
    gc = bitmap.create_gc(foreground=0, background=0)
    bitmap.fill_rectangle(gc, 0, 0, arc, arc)
    gc.change(foreground=1)
    for y in range(arc):
        for x in range(arc):
            if alpha[x, y] > 0:
                bitmap.fill_rectangle(gc, x, y, 1, 1)
    gc.free()
    return bitmap


def run_linux(monitors, arc):
    try:
        from Xlib import display as Xdisplay, X
        from Xlib.ext import shape
    except ImportError:
        print("ERROR: Linux requires:  pip install python-xlib")
        sys.exit(1)

    xdpy       = Xdisplay.Display()
    screen_num = xdpy.get_default_screen()
    xscreen    = xdpy.screen(screen_num)
    root       = xscreen.root
    ATOM       = xdpy.intern_atom("ATOM")

    # The 4 corner shapes are identical regardless of which monitor they sit
    # on, so build each mask exactly once and reuse it for every monitor.
    masks = {c: _build_shape_mask(root, arc, c) for c in ("tl", "tr", "bl", "br")}

    windows = []
    for (mx, my, mw, mh) in monitors:
        print(f"  Monitor {mw}x{mh} @ ({mx},{my})")
        positions = {
            "tl": (mx,            my),
            "tr": (mx + mw - arc, my),
            "bl": (mx,            my + mh - arc),
            "br": (mx + mw - arc, my + mh - arc),
        }
        for corner, (wx, wy) in positions.items():
            win = root.create_window(
                wx, wy, arc, arc, 0,
                xscreen.root_depth,
                X.InputOutput,
                X.CopyFromParent,
                background_pixel=xscreen.black_pixel,  # server auto-paints this,
                event_mask=X.ExposureMask,              # so no redraw code needed
                override_redirect=True,
            )
            win.change_property(xdpy.intern_atom("_NET_WM_WINDOW_TYPE"), ATOM, 32,
                                 [xdpy.intern_atom("_NET_WM_WINDOW_TYPE_DOCK")])
            win.change_property(xdpy.intern_atom("_NET_WM_STATE"), ATOM, 32, [
                xdpy.intern_atom("_NET_WM_STATE_ABOVE"),
                xdpy.intern_atom("_NET_WM_STATE_SKIP_TASKBAR"),
                xdpy.intern_atom("_NET_WM_STATE_SKIP_PAGER"),
            ])
            win.map()
            win.shape_mask(shape.SO.Set, shape.SK.Bounding, 0, 0, masks[corner])
            windows.append(win)

    xdpy.sync()
    print(f"\n{len(windows)} static corner overlays active in a single process "
          f"(no pygame). Ctrl-C to quit.")

    try:
        signal.pause()  # blocks at ~0% CPU until a signal (e.g. Ctrl-C) arrives
    except AttributeError:
        # signal.pause() isn't available on every platform - fall back safely
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    except KeyboardInterrupt:
        pass
    sys.exit(0)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Rounded-corner overlay for every connected monitor.")
    parser.add_argument("--arc", type=int, default=40,
                        help="Corner arc radius in pixels (default: 40)")
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
