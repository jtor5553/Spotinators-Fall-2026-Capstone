#!/bin/bash
# Wait for the local controller page, then open it in a browser.
set -u

URL="${SPOT_CONE_URL:-http://127.0.0.1:8000}"

if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
  echo "No graphical session; not opening a browser." >&2
  exit 0
fi

ready=0
for _ in $(seq 1 90); do
  if curl -fsS -o /dev/null --max-time 1 "$URL/"; then
    ready=1
    break
  fi
  sleep 1
done

if [ "$ready" -ne 1 ]; then
  echo "Controller page did not respond at $URL" >&2
  exit 1
fi

if command -v flatpak >/dev/null 2>&1 && flatpak info org.chromium.Chromium >/dev/null 2>&1; then
  exec flatpak run org.chromium.Chromium --new-window "$URL"
fi
if command -v chromium-browser >/dev/null 2>&1; then
  exec chromium-browser --new-window "$URL"
fi
if command -v chromium >/dev/null 2>&1; then
  exec chromium --new-window "$URL"
fi
if command -v google-chrome >/dev/null 2>&1; then
  exec google-chrome --new-window "$URL"
fi

exec xdg-open "$URL"
