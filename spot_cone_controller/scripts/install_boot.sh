#!/bin/bash
# Install the controller so it starts at boot and the page opens in a browser.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -E bash "$0" "$@"
fi

REAL_USER="${SUDO_USER:-}"
if [ -z "$REAL_USER" ] || [ "$REAL_USER" = "root" ]; then
  echo "Run this script as the desktop user: sudo bash scripts/install_boot.sh" >&2
  exit 1
fi

REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
  echo "Missing $APP_DIR/.venv/bin/python. Create the virtual environment first." >&2
  exit 1
fi

sed \
  -e "s|REPLACE_WITH_JETSON_USERNAME|${REAL_USER}|g" \
  -e "s|REPLACE_WITH_APP_DIR|${APP_DIR}|g" \
  "$APP_DIR/deploy/spot-cone-controller.service" \
  > /etc/systemd/system/spot-cone-controller.service

if [ -f "$APP_DIR/deploy/99-dualsense.rules" ]; then
  install -m 0644 "$APP_DIR/deploy/99-dualsense.rules" /etc/udev/rules.d/99-dualsense.rules
  udevadm control --reload-rules || true
  udevadm trigger --subsystem-match=input || true
fi

usermod -aG input,bluetooth "$REAL_USER"

if ! command -v chromium-browser >/dev/null 2>&1 \
  && ! command -v chromium >/dev/null 2>&1 \
  && ! command -v google-chrome >/dev/null 2>&1 \
  && ! flatpak info org.chromium.Chromium >/dev/null 2>&1; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y flatpak
  flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
  flatpak install -y flathub org.chromium.Chromium
fi

install -d -o "$REAL_USER" -g "$REAL_USER" -m 0755 "$REAL_HOME/.config/autostart"
sed "s|REPLACE_WITH_APP_DIR|${APP_DIR}|g" \
  "$APP_DIR/deploy/spot-cone-browser.desktop" \
  > "$REAL_HOME/.config/autostart/spot-cone-browser.desktop"
chown "$REAL_USER:$REAL_USER" "$REAL_HOME/.config/autostart/spot-cone-browser.desktop"
chmod 0644 "$REAL_HOME/.config/autostart/spot-cone-browser.desktop"
chmod 0755 "$APP_DIR/scripts/open_gui_browser.sh"

systemctl daemon-reload
systemctl enable --now spot-cone-controller.service

UID_NUM="$(id -u "$REAL_USER")"
RUNTIME="/run/user/${UID_NUM}"

# A login service would bind the same port. The boot service replaces it.
if [ -d "$RUNTIME" ]; then
  sudo -u "$REAL_USER" \
    XDG_RUNTIME_DIR="$RUNTIME" \
    systemctl --user disable --now spot-cone-controller.service || true
fi
if [ -d "$RUNTIME" ]; then
  DISPLAY_VALUE=":0"
  XAUTHORITY_VALUE=""
  shell_pid="$(pgrep -u "$REAL_USER" -n gnome-shell || true)"
  if [ -n "$shell_pid" ] && [ -r "/proc/${shell_pid}/environ" ]; then
    while IFS= read -r -d '' entry; do
      case "$entry" in
        DISPLAY=*) DISPLAY_VALUE="${entry#DISPLAY=}" ;;
        XAUTHORITY=*) XAUTHORITY_VALUE="${entry#XAUTHORITY=}" ;;
      esac
    done < "/proc/${shell_pid}/environ"
  fi
  sudo -u "$REAL_USER" \
    DISPLAY="$DISPLAY_VALUE" \
    XAUTHORITY="$XAUTHORITY_VALUE" \
    XDG_RUNTIME_DIR="$RUNTIME" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=${RUNTIME}/bus" \
    "$APP_DIR/scripts/open_gui_browser.sh"
fi

systemctl --no-pager --full status spot-cone-controller.service
