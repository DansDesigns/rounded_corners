#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

echo "Installing Rounded Corners..."

# Interactive installs create launcher/autostart files for the desktop user.
# The Alternix live-preview ISO is different: the OS installer prebuilds
# the complete desktop as root in a chroot, intentionally writes the user's
# template into /root, then copies it into /etc/skel and the Live account.
# The explicit flag is set only for that build by build-iso.sh.
ISO_PREBUILD=0
if [ "${ALTERNIX_ISO_PREBUILD:-0}" = 1 ]; then
    if [ "$(id -u)" -ne 0 ] || [ "${TARGET_USER:-}" != root ] || [ "${HOME:-}" != /root ]; then
        echo 'ERROR: Rounded Corners ISO prebuild requires root, TARGET_USER=root, HOME=/root.' >&2
        exit 1
    fi
    ISO_PREBUILD=1
fi

# Reject ordinary sudo invocation: otherwise the desktop shortcut would
# land in /root instead of the signed-in user's home. SUDO_USER=root can
# legitimately occur when the root-based ISO prebuild invokes sudo itself.
if [ "$(id -u)" -eq 0 ] && [ "$ISO_PREBUILD" -ne 1 ] && \
   [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != root ]; then
    echo 'ERROR: Run install_corners.sh as the desktop user, not with sudo.' >&2
    exit 1
fi

# Do not invoke osm-sudo from inside the root-owned build chroot: there is
# no graphical pattern/PIN session. Ordinary users still use Alternix's
# osm-sudo authentication, and non-Alternix systems use normal sudo.
elevate() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v osm-sudo >/dev/null 2>&1; then
        osm-sudo "$@"
    else
        sudo "$@"
    fi
}

# This application lives in /usr/bin, not AlternixDE's private Qtile venv.
# Install/test dependencies against the interpreter used by its launchers.
SYSTEM_PYTHON=/usr/bin/python3
[ -x "$SYSTEM_PYTHON" ] || {
    echo 'ERROR: System Python /usr/bin/python3 is required.' >&2
    exit 1
}

# tkinter powers the settings window. The overlay itself needs no tkinter.
if ! "$SYSTEM_PYTHON" -c 'import tkinter' >/dev/null 2>&1; then
    elevate apt-get install -y python3-tk
fi

# Install only missing dependencies. --break-system-packages is needed on
# newer Debian/Devuan releases for system Python; don't modify the Qtile venv.
if ! "$SYSTEM_PYTHON" -c 'from PIL import Image; import screeninfo; from Xlib import display' >/dev/null 2>&1; then
    elevate "$SYSTEM_PYTHON" -m pip install --break-system-packages pillow screeninfo python-xlib
fi

# Update the actual app, not a separate patch/fix script.
elevate install -m 755 rounded_corners.py /usr/bin/rounded_corners

if [ -f "corners.png" ]; then
    elevate mkdir -p /usr/share/icons/hicolor/64x64/apps
    elevate cp corners.png /usr/share/icons/hicolor/64x64/apps/corners.png
fi

# Examine the existing autostart entry before changing it. In older installs
# ~/.config/autostart may itself be a file: the Python installer recognises
# that legacy Rounded Corners entry and safely migrates it, leaving other
# applications' files untouched. Existing correct entries are not rewritten.
# Settings remain in the actual desktop user's home directory.
"$SYSTEM_PYTHON" /usr/bin/rounded_corners --install-shortcuts

# An ISO chroot has no X server. Starting an overlay here cannot draw
# anything and should not leave a root-owned background process behind.
# New users receive the launchers through /etc/skel and autostart runs
# their own overlay when they actually log in.
if [ "$ISO_PREBUILD" -eq 1 ]; then
    echo 'Rounded Corners prepared for the ISO user template; overlay deferred until login.'
elif [ -n "${DISPLAY:-}" ]; then
    "$SYSTEM_PYTHON" /usr/bin/rounded_corners --overlay >/dev/null 2>&1 </dev/null &
fi

echo "Installed. Open 'Rounded Corners' from your app launcher to configure."
