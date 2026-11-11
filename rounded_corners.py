#!/usr/bin/env python3
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
    python rounded_corners.py --settings   # graphical settings (launcher entry)
    python rounded_corners.py --overlay    # background corner overlay (autostart)
    python rounded_corners.py --arc 60     # legacy overlay command (60 px)
"""

import argparse
import sys
import platform
import os
import json
import subprocess
import time
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"
MIN_ARC = 5
MAX_ARC = 300
DEFAULTS = {"arc": 40, "enabled": True, "start_on_boot": True}


def settings_folder():
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "RoundedCorners"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "rounded_corners"


def settings_path():
    return settings_folder() / "settings.json"


def clamp_arc(value):
    try:
        return max(MIN_ARC, min(MAX_ARC, int(float(value))))
    except (ValueError, TypeError, OverflowError):
        return DEFAULTS["arc"]


def load_settings():
    data = dict(DEFAULTS)
    try:
        with settings_path().open("r", encoding="utf-8") as stream:
            stored = json.load(stream)
        if isinstance(stored, dict):
            data["arc"] = clamp_arc(stored.get("arc", data["arc"]))
            for key in ("enabled", "start_on_boot"):
                if type(stored.get(key)) is bool:
                    data[key] = stored[key]
    except (OSError, ValueError):
        pass
    return data


def save_settings(data):
    folder = settings_folder()
    folder.mkdir(parents=True, exist_ok=True)
    path = settings_path()
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


def script_path():
    return str(Path(__file__).resolve())


def python_command(background=False):
    exe = Path(sys.executable)
    if IS_WINDOWS and background:
        hidden = exe.with_name("pythonw.exe")
        if hidden.is_file():
            exe = hidden
    return str(exe)


def startup_path():
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "rounded_corners.lnk"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart" / "rounded_corners.desktop"


def _desktop_entry(overlay=False):
    # This file is created in each user's home: no root privileges required.
    command = "--overlay" if overlay else "--settings"
    return ("[Desktop Entry]\n"
            "Version=1.0\nType=Application\n"
            "Name=Rounded Corners\n"
            "Comment=Configure rounded monitor corners\n"
            f"Exec={python_command()} {script_path()} {command}\n"
            "Icon=corners\nTerminal=false\nCategories=Utility;Settings;\n"
            "StartupNotify=false\n")


def _windows_shortcut(path, command):
    # Windows' built-in WScript.Shell COM object creates proper .lnk files.
    import base64

    def quoted(value):
        return "'" + str(value).replace("'", "''") + "'"

    path.parent.mkdir(parents=True, exist_ok=True)
    script = ("$shell = New-Object -ComObject WScript.Shell; "
              f"$link = $shell.CreateShortcut({quoted(path)}); "
              f"$link.TargetPath = {quoted(python_command(background=True))}; "
              f"$link.Arguments = {quoted('\"' + script_path() + '\" ' + command)}; "
              f"$link.WorkingDirectory = {quoted(str(Path(script_path()).parent))}; "
              "$link.WindowStyle = 7; $link.Save()")
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Unable to create Windows shortcut")


def sync_startup(enabled):
    path = startup_path()
    if not enabled:
        path.unlink(missing_ok=True)
        return
    if IS_WINDOWS:
        _windows_shortcut(path, "--overlay")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_desktop_entry(overlay=True), encoding="utf-8")


def install_shortcuts():
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        menu = base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Rounded Corners.lnk"
        _windows_shortcut(menu, "--settings")
    else:
        menu = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "applications" / "rounded_corners.desktop"
        menu.parent.mkdir(parents=True, exist_ok=True)
        menu.write_text(_desktop_entry(overlay=False), encoding="utf-8")
    sync_startup(load_settings()["start_on_boot"])


def _spawn_overlay():
    cmd = [python_command(background=True), script_path(), "--overlay"]
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
              "stderr": subprocess.DEVNULL}
    if IS_WINDOWS:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, **kwargs)


def _acquire_overlay_lock():
    """One overlay process per user/session; never close another process by PID."""
    folder = settings_folder()
    folder.mkdir(parents=True, exist_ok=True)
    handle = (folder / "overlay.lock").open("a+b")
    try:
        if IS_WINDOWS:
            import msvcrt
            if not handle.seek(0, 2):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError):
        handle.close()
        return None
    return handle


def settings_stamp():
    try:
        return settings_path().stat().st_mtime_ns
    except OSError:
        return None


def show_settings():
    """A small cross-platform configuration window; the overlay runs separately."""
    import tkinter as tk
    from tkinter import ttk, messagebox

    current = load_settings()
    root = tk.Tk()
    root.title("Rounded Corners Settings")
    root.geometry("460x440")
    root.minsize(440, 420)
    root.configure(bg="#1d222b")

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    style.configure("App.TFrame", background="#1d222b")
    style.configure("App.TLabel", background="#1d222b", foreground="#e6ebf3", font=("Arial", 10))
    style.configure("Hint.TLabel", background="#1d222b", foreground="#a9b4c6", font=("Arial", 9))
    style.configure("App.TCheckbutton", background="#1d222b", foreground="#e6ebf3", font=("Arial", 10))
    style.map("App.TCheckbutton", background=[("active", "#1d222b")])
    style.configure("App.Horizontal.TScale", background="#1d222b")
    style.configure("App.TButton", padding=(16, 7))

    panel = ttk.Frame(root, style="App.TFrame", padding=(22, 18))
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text="Rounded Corners", style="App.TLabel",
              font=("Arial", 16, "bold")).pack(anchor="w")
    ttk.Label(panel, text="Adjust the corner masks on every monitor.",
              style="Hint.TLabel").pack(anchor="w", pady=(3, 12))

    preview = tk.Canvas(panel, width=396, height=128, bg="#101419",
                        highlightthickness=0)
    preview.pack(fill="x", pady=(0, 15))

    def draw_rounded_rectangle(canvas, x1, y1, x2, y2, radius, fill):
        radius = max(2, min(int(radius), int((x2-x1)/2), int((y2-y1)/2)))
        canvas.create_rectangle(x1+radius, y1, x2-radius, y2, fill=fill, outline="")
        canvas.create_rectangle(x1, y1+radius, x2, y2-radius, fill=fill, outline="")
        for x, y in ((x1, y1), (x2-2*radius, y1),
                     (x1, y2-2*radius), (x2-2*radius, y2-2*radius)):
            canvas.create_oval(x, y, x+2*radius, y+2*radius, fill=fill, outline="")

    arc_var = tk.IntVar(value=current["arc"])
    show_var = tk.BooleanVar(value=current["enabled"])
    boot_var = tk.BooleanVar(value=current["start_on_boot"])
    radius_label = ttk.Frame(panel, style="App.TFrame")
    radius_label.pack(fill="x")
    ttk.Label(radius_label, text="Corner radius", style="App.TLabel").pack(side="left")
    entry = tk.Spinbox(radius_label, from_=MIN_ARC, to=MAX_ARC, increment=1,
                       textvariable=arc_var, width=5, justify="center",
                       bg="#303746", fg="white", insertbackground="white",
                       buttonbackground="#445063", relief="flat")
    entry.pack(side="right")
    ttk.Label(radius_label, text="px", style="Hint.TLabel").pack(side="right", padx=(0, 7))

    scale = ttk.Scale(panel, from_=MIN_ARC, to=MAX_ARC,
                      style="App.Horizontal.TScale", orient="horizontal")
    scale.pack(fill="x", pady=(8, 13))
    scale.set(current["arc"])
    syncing = False

    def draw_preview(*_):
        preview.delete("all")
        width = max(200, preview.winfo_width())
        radius = clamp_arc(arc_var.get()) if str(arc_var.get()).strip() else 40
        drawn_radius = min(54, max(5, int(radius * .28)))
        draw_rounded_rectangle(preview, 14, 8, width-14, 120,
                               drawn_radius, "#536780")
        preview.create_text(width/2, 62, text="Screen preview",
                            fill="#e6edf7", font=("Arial", 11))

    def slider_changed(value):
        nonlocal syncing
        if syncing:
            return
        syncing = True
        arc_var.set(int(round(float(value))))
        syncing = False
        draw_preview()

    def entry_changed(*_):
        nonlocal syncing
        if syncing:
            return
        try:
            value = int(arc_var.get())
        except (tk.TclError, ValueError):
            return
        syncing = True
        scale.set(max(MIN_ARC, min(MAX_ARC, value)))
        syncing = False
        draw_preview()

    scale.configure(command=slider_changed)
    arc_var.trace_add("write", entry_changed)
    preview.bind("<Configure>", draw_preview)

    ttk.Checkbutton(panel, text="Enable rounded corners now", variable=show_var,
                    style="App.TCheckbutton").pack(anchor="w", pady=(4, 8))
    ttk.Checkbutton(panel, text="Start automatically when I sign in", variable=boot_var,
                    style="App.TCheckbutton").pack(anchor="w")
    ttk.Label(panel, text="Login startup runs the overlay, not this settings window.",
              style="Hint.TLabel", wraplength=390).pack(anchor="w", pady=(4, 12))

    status = ttk.Label(panel, text="", style="Hint.TLabel")
    status.pack(anchor="w")
    buttons = ttk.Frame(panel, style="App.TFrame")
    buttons.pack(fill="x", side="bottom", pady=(10, 0))

    def apply():
        try:
            value = int(entry.get())
        except (TypeError, ValueError):
            messagebox.showerror("Invalid radius", "Enter a radius in pixels (5-300).", parent=root)
            return False
        if value < MIN_ARC or value > MAX_ARC:
            messagebox.showerror("Invalid radius", "Choose a radius from 5 to 300 pixels.", parent=root)
            return False
        data = {"arc": value, "enabled": bool(show_var.get()),
                "start_on_boot": bool(boot_var.get())}
        try:
            sync_startup(data["start_on_boot"])
            save_settings(data)
            if data["enabled"]:
                _spawn_overlay()  # a second instance exits immediately if already running
        except (OSError, RuntimeError) as exc:
            messagebox.showerror("Could not save settings", str(exc), parent=root)
            return False
        status.configure(text="Applied — changes take effect without signing out.")
        return True

    ttk.Button(buttons, text="Close", command=root.destroy,
               style="App.TButton").pack(side="right")
    ttk.Button(buttons, text="Apply", command=apply,
               style="App.TButton").pack(side="right", padx=(0, 10))
    root.mainloop()


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

    def create_corners(new_arc):
        for win in all_wins:
            try:
                win.destroy()
            except tk.TclError:
                pass
        all_wins.clear()
        for (mx, my, mw, mh) in monitors:
            positions = {
                "tl": (mx,              my),
                "tr": (mx + mw - new_arc, my),
                "bl": (mx,              my + mh - new_arc),
                "br": (mx + mw - new_arc, my + mh - new_arc),
            }
            for key, (wx, wy) in positions.items():
                photo = make_photo(new_arc, key)
                win = tk.Toplevel(root)
                win.overrideredirect(True)
                win.attributes("-topmost", True)
                win.geometry(f"{new_arc}x{new_arc}+{wx}+{wy}")
                win.attributes("-transparentcolor", TKEY)
                win.configure(bg=TKEY)
                canvas = tk.Canvas(win, width=new_arc, height=new_arc,
                                   bg=TKEY, highlightthickness=0)
                canvas.pack()
                canvas.create_image(0, 0, anchor="nw", image=photo)
                canvas._ref = photo
                all_wins.append(win)

    create_corners(arc)

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

    last_stamp = settings_stamp()
    current_arc = arc

    def check_settings():
        nonlocal last_stamp, current_arc
        stamp = settings_stamp()
        if stamp != last_stamp:
            last_stamp = stamp
            updated = load_settings()
            if not updated["enabled"]:
                root.quit()
                return
            if updated["arc"] != current_arc:
                current_arc = updated["arc"]
                create_corners(current_arc)
        root.after(350, check_settings)

    root.after(350, check_settings)
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
        root.destroy()


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

    windows = []
    masks = {}

    def create_corners(new_arc):
        nonlocal masks
        for win in windows:
            try:
                win.destroy()
            except Exception:
                pass
        windows.clear()
        for mask in masks.values():
            try:
                mask.free()
            except Exception:
                pass
        masks = {c: _build_shape_mask(root, new_arc, c)
                 for c in ("tl", "tr", "bl", "br")}

        for (mx, my, mw, mh) in monitors:
            positions = {
                "tl": (mx,                  my),
                "tr": (mx + mw - new_arc,  my),
                "bl": (mx,                  my + mh - new_arc),
                "br": (mx + mw - new_arc, my + mh - new_arc),
            }
            for corner, (wx, wy) in positions.items():
                win = root.create_window(
                    wx, wy, new_arc, new_arc, 0, xscreen.root_depth,
                    X.InputOutput, X.CopyFromParent,
                    background_pixel=xscreen.black_pixel,
                    event_mask=X.ExposureMask,
                    override_redirect=True,
                )
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
                win.shape_mask(shape_operation_set, shape_region_bounding,
                               0, 0, masks[corner])
                windows.append(win)
        xdpy.sync()

    create_corners(arc)

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

    import select
    current_arc = arc
    last_stamp = settings_stamp()
    try:
        while True:
            # Listen for X11 restacks while also checking for settings edits.
            # select() sleeps between events: no continuous repainting.
            select.select([xdpy.fileno()], [], [], .35)
            while xdpy.pending_events():
                event = xdpy.next_event()
                if handle_stacking_event(event):
                    for corner_window in windows:
                        corner_window.configure(stack_mode=X.Above)
                    xdpy.flush()

            stamp = settings_stamp()
            if stamp != last_stamp:
                last_stamp = stamp
                updated = load_settings()
                if not updated["enabled"]:
                    break
                if updated["arc"] != current_arc:
                    current_arc = updated["arc"]
                    create_corners(current_arc)
                    corner_ids = {win.id for win in windows}
    except KeyboardInterrupt:
        pass
    finally:
        for corner_window in windows:
            try:
                corner_window.destroy()
            except Exception:
                pass
        for mask in masks.values():
            try:
                mask.free()
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
        description="Rounded corners: settings window or desktop overlay.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--settings", action="store_true", help="Open settings window")
    modes.add_argument("--overlay", action="store_true", help="Run desktop overlay")
    modes.add_argument("--install-shortcuts", action="store_true",
                       help="Install/update application menu and autostart shortcuts")
    parser.add_argument("--arc", type=int, default=None,
                        help="Optional radius override for this session (5-300 px)")
    args = parser.parse_args()

    if args.install_shortcuts:
        install_shortcuts()
        return
    if args.settings:
        show_settings()
        return

    # Keep legacy `python rounded_corners.py` running the overlay, not a GUI.
    config = load_settings()
    if not config["enabled"]:
        return
    lock = _acquire_overlay_lock()
    if lock is None:
        return  # Already running; don't layer duplicate masks on monitors.

    arc = clamp_arc(args.arc if args.arc is not None else config["arc"])
    print(f"Rounded corners overlay | arc = {arc} px | "
          f"{'Windows' if IS_WINDOWS else 'Linux'}")

    monitors = get_monitors()
    if not monitors:
        if IS_WINDOWS:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            monitors = [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]
            root.destroy()
        else:
            import re
            try:
                out = subprocess.check_output(["xrandr"], text=True)
                monitors = [(int(x), int(y), int(w), int(h))
                            for w, h, x, y in re.findall(
                                r"(\d+)x(\d+)\+(\d+)\+(\d+)", out)]
            except Exception:
                monitors = [(0, 0, 1920, 1080)]

    try:
        if IS_WINDOWS:
            run_windows(monitors, arc)
        else:
            run_linux(monitors, arc)
    finally:
        lock.close()


if __name__ == "__main__":
    main()
