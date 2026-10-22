"""
rounded_corners.py
------------------
Draws pure-black rounded-corner overlays on every connected monitor.
Always on top, variable arc radius - identical to the macOS corner effect.

Windows : uses tkinter + transparentcolor and a Win32 window-stacking event hook.
Linux   : uses raw Xlib + the X SHAPE extension, in a single lightweight process.
          The corner masks remain static, but stacking events immediately return
          them to the top if Freehand or another overlay raises itself.
          No pygame/SDL2 or continuous repaint loop.

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
#  Watch z-order events so Freehand's regular HWND_TOPMOST reassertion cannot
#  hide the corners for up to two seconds between the old pulse() calls.
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

    # Freehand (and other apps) can call SetWindowPos(HWND_TOPMOST) every
    # fraction of a second. A 2-second poll makes the masks visibly disappear.
    # Instead, WinEventHook notifies us immediately when OTHER processes change
    # stacking order, and Tk's existing GUI thread restores the mask windows.
    pending_restack = False

    def raise_corners():
        nonlocal pending_restack
        pending_restack = False
        for w in all_wins:
            try:
                if w.winfo_exists():
                    w.attributes("-topmost", True)
                    w.lift()
            except tk.TclError:
                pass

    def request_restack():
        nonlocal pending_restack
        if pending_restack:
            return
        pending_restack = True
        try:
            root.after_idle(raise_corners)
        except tk.TclError:
            pending_restack = False

    win_event_hook = None
    win_event_callback = None
    user32 = None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        # EVENT_OBJECT_REORDER: a window was raised/lowered.
        # EVENT_OBJECT_SHOW: another program just created/shown an overlay.
        # WINEVENT_SKIPOWNPROCESS avoids an infinite feedback loop from lift().
        callback_type = ctypes.WINFUNCTYPE(
            None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
            ctypes.c_long, ctypes.c_long, wintypes.DWORD, wintypes.DWORD)
        user32.SetWinEventHook.argtypes = (
            wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, callback_type,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD)
        user32.SetWinEventHook.restype = wintypes.HANDLE
        user32.UnhookWinEvent.argtypes = (wintypes.HANDLE,)
        user32.UnhookWinEvent.restype = wintypes.BOOL

        @callback_type
        def on_stacking_change(_hook, _event, _hwnd, object_id,
                               child_id, _thread, _when):
            if object_id == 0 and child_id == 0:  # OBJID_WINDOW/CHILDID_SELF
                request_restack()

        win_event_callback = on_stacking_change  # keep CFUNCTYPE alive
        win_event_hook = user32.SetWinEventHook(
            0x8002, 0x8004, None, win_event_callback, 0, 0,
            0x0000 | 0x0002)  # OUTOFCONTEXT | SKIPOWNPROCESS
        if not win_event_hook:
            print("Windows stacking hook unavailable; using fast topmost check.")
    except (OSError, AttributeError, ValueError, TypeError) as exc:
        print("Windows stacking hook unavailable:", exc)

    def pulse():
        # The event hook is the normal route (effectively immediate). A slow
        # backup check also covers applications which don't emit reorder events.
        raise_corners()
        try:
            root.after(900 if win_event_hook else 100, pulse)
        except tk.TclError:
            pass

    pulse()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        if win_event_hook and user32 is not None:
            try:
                user32.UnhookWinEvent(win_event_hook)
            except (OSError, AttributeError):
                pass


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

    # python-xlib exposes SHAPE constants as ShapeSet/ShapeBounding on some
    # releases and SO.Set/SK.Bounding on others. Accept both (no new dependency).
    shape_operation_set = getattr(getattr(shape, "SO", None), "Set",
                                  getattr(shape, "ShapeSet", 0))
    shape_region_bounding = getattr(getattr(shape, "SK", None), "Bounding",
                                    getattr(shape, "ShapeBounding", 0))

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
            # Identify these unmanaged windows for desktop tools/debugging.
            # They remain override-redirect, so Qtile cannot take control.
            win.set_wm_name("Freehand Rounded Corners")
            win.set_wm_class("rounded_corners", "FreehandRoundedCorners")
            win.change_property(xdpy.intern_atom("_NET_WM_WINDOW_TYPE"), ATOM, 32,
                                 [xdpy.intern_atom("_NET_WM_WINDOW_TYPE_DOCK")])
            win.change_property(xdpy.intern_atom("_NET_WM_STATE"), ATOM, 32, [
                xdpy.intern_atom("_NET_WM_STATE_ABOVE"),
                xdpy.intern_atom("_NET_WM_STATE_SKIP_TASKBAR"),
                xdpy.intern_atom("_NET_WM_STATE_SKIP_PAGER"),
            ])
            win.map()
            win.shape_mask(shape_operation_set, shape_region_bounding, 0, 0, masks[corner])
            windows.append(win)

    # Subscribe to restacks of TOP-LEVEL X11 windows. In particular, Freehand
    # uses XRaiseWindow about eight times a second to remain visible above
    # Alternix's launcher; without this listener it ends up covering the corner
    # masks. X11 reports each foreign restack as ConfigureNotify on the root.
    # Selecting this mask is per-client and does not interfere with Qtile's masks.
    root.change_attributes(event_mask=X.SubstructureNotifyMask)
    corner_ids = {win.id for win in windows}
    xdpy.sync()
    print(f"\n{len(windows)} rounded corner masks active above desktop overlays "
          "(event-driven, no continuous redraw). Ctrl-C to quit.")

    def handle_stacking_event(event):
        """Return True only if another root-level window changed z-order."""
        if event.type not in (X.ConfigureNotify, X.MapNotify):
            return False
        affected = getattr(event, "window", None)
        if affected is None:
            return False
        affected_id = getattr(affected, "id", affected)
        return affected_id not in corner_ids

    try:
        while True:
            # next_event() sleeps on the X server socket; ~0% idle CPU.
            event = xdpy.next_event()
            if handle_stacking_event(event):
                # Raise all four corners as one group. Their own ConfigureNotify
                # events are ignored, preventing any self-induced raise loop.
                for corner_window in windows:
                    corner_window.configure(stack_mode=X.Above)
                xdpy.flush()
    except KeyboardInterrupt:
        pass
    finally:
        # Normal X11 resource teardown; avoid leaving orphaned black masks.
        for corner_window in windows:
            try:
                corner_window.destroy()
            except Exception:
                pass
        try:
            xdpy.close()
        except Exception:
            pass


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
