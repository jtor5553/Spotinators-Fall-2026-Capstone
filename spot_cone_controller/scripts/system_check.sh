#!/usr/bin/env bash
# Phase 0 read-only check for the Spot cone-controller Jetson.
# Does not install packages, change network or radio state, or control hardware.

set -u

hr() {
  printf '%s\n' "==================================="
}

have() {
  command -v "$1" >/dev/null 2>&1
}

run_capture() {
  if ! have "$1"; then
    printf 'COMMAND NOT FOUND: %s\n' "$1"
    return 0
  fi
  if have timeout; then
    timeout 8s "$@"
  else
    "$@"
  fi
  local status=$?
  if [ "$status" -eq 124 ]; then
    printf 'TIMED OUT: %s\n' "$*"
  elif [ "$status" -ne 0 ]; then
    printf 'EXIT STATUS: %s\n' "$status"
  fi
  return 0
}

estimate_jetpack() {
  case "$1" in
    35.1|35.1.*) printf '%s\n' "ESTIMATED JetPack 5.0.2 from L4T $1" ;;
    35.2|35.2.*) printf '%s\n' "ESTIMATED JetPack 5.1 from L4T $1" ;;
    35.3|35.3.*) printf '%s\n' "ESTIMATED JetPack 5.1.1 from L4T $1" ;;
    35.4|35.4.*) printf '%s\n' "ESTIMATED JetPack 5.1.2 from L4T $1" ;;
    35.5|35.5.*) printf '%s\n' "ESTIMATED JetPack 5.1.3 from L4T $1" ;;
    35.6|35.6.*) printf '%s\n' "ESTIMATED JetPack 5.1.4 from L4T $1" ;;
    36.2|36.2.*) printf '%s\n' "ESTIMATED JetPack 6.0 Developer Preview from L4T $1" ;;
    36.3|36.3.*) printf '%s\n' "ESTIMATED JetPack 6.0 from L4T $1" ;;
    36.4.0) printf '%s\n' "ESTIMATED JetPack 6.1 from L4T $1" ;;
    36.4.3) printf '%s\n' "ESTIMATED JetPack 6.2 from L4T $1" ;;
    36.4.4) printf '%s\n' "ESTIMATED JetPack 6.2.1 from L4T $1" ;;
    36.4|36.4.*) printf '%s\n' "ESTIMATED JetPack 6.1 or 6.2.x from L4T $1; confirm the raw L4T line" ;;
    *) printf '%s\n' "UNKNOWN (no nvidia-jetpack package; L4T $1 is not in the local estimate table)" ;;
  esac
}

OS_PRETTY="UNKNOWN"
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_PRETTY="${PRETTY_NAME:-UNKNOWN}"
fi

KERNEL="$(uname -r 2>/dev/null || printf '%s' "UNKNOWN")"
ARCH="$(uname -m 2>/dev/null || printf '%s' "UNKNOWN")"
HOST_NAME="$(hostname 2>/dev/null || printf '%s' "UNKNOWN")"

if have python3; then
  PYTHON="$(python3 --version 2>&1)"
else
  PYTHON="NOT FOUND"
fi

if [ -r /proc/device-tree/model ]; then
  MODEL="$(tr -d '\0' < /proc/device-tree/model)"
else
  MODEL="UNKNOWN (no /proc/device-tree/model)"
fi

if [ -r /etc/nv_tegra_release ]; then
  L4T_RAW="$(head -n 1 /etc/nv_tegra_release)"
else
  L4T_RAW="NOT FOUND"
fi

L4T_VERSION="UNKNOWN"
if [[ "$L4T_RAW" =~ R([0-9]+).*REVISION:[[:space:]]*([0-9.]+) ]]; then
  L4T_VERSION="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}"
fi

JETPACK_PKG="NOT INSTALLED"
L4T_PKG="NOT INSTALLED"
if have dpkg-query; then
  jp_out="$(dpkg-query -W -f='${Version}' nvidia-jetpack 2>/dev/null || true)"
  l4t_out="$(dpkg-query -W -f='${Version}' nvidia-l4t-core 2>/dev/null || true)"
  if [ -n "$jp_out" ]; then
    JETPACK_PKG="$jp_out"
  fi
  if [ -n "$l4t_out" ]; then
    L4T_PKG="$l4t_out"
  fi
fi

if [ "$JETPACK_PKG" != "NOT INSTALLED" ]; then
  JETPACK_ESTIMATE="not needed; nvidia-jetpack package is installed"
else
  JETPACK_ESTIMATE="$(estimate_jetpack "$L4T_VERSION")"
fi

RAM_SUMMARY="UNKNOWN"
if have free; then
  RAM_SUMMARY="$(free -h | awk '/^Mem:/ {print $2 " total, " $7 " available"}')"
fi
if [ -z "$RAM_SUMMARY" ] || [ "$RAM_SUMMARY" = "UNKNOWN" ]; then
  if [ -r /proc/meminfo ]; then
    mem_total="$(awk '/^MemTotal:/ {print $2, $3}' /proc/meminfo)"
    mem_avail="$(awk '/^MemAvailable:/ {print $2, $3}' /proc/meminfo)"
    RAM_SUMMARY="${mem_total} total, ${mem_avail} available"
  fi
fi

DISK_FREE="UNKNOWN"
if have df; then
  DISK_FREE="$(df -h / | awk 'NR==2 {print $4 " free of " $2 " on " $6 " (" $5 " used)"}')"
fi

ETH_DETAILS=""
WIFI_DETAILS=""
OTHER_DETAILS=""
shopt -s nullglob
for path in /sys/class/net/*; do
  name="${path##*/}"
  if [ "$name" = "lo" ]; then
    continue
  fi
  iftype="unknown"
  oper="unknown"
  mac="unknown"
  carrier="unavailable"
  if [ -r "$path/type" ]; then
    iftype="$(cat "$path/type")"
  fi
  if [ -r "$path/operstate" ]; then
    oper="$(cat "$path/operstate")"
  fi
  if [ -r "$path/address" ]; then
    mac="$(cat "$path/address")"
  fi
  if [ -r "$path/carrier" ]; then
    carrier="$(cat "$path/carrier" 2>/dev/null || true)"
    if [ -z "$carrier" ]; then
      carrier="unavailable"
    fi
  fi
  ipv4=""
  while read -r addr; do
    if [ -z "$addr" ]; then
      continue
    fi
    if [ -z "$ipv4" ]; then
      ipv4="$addr"
    else
      ipv4="$ipv4, $addr"
    fi
  done < <(ip -4 -o addr show dev "$name" 2>/dev/null | awk '{print $4}')
  if [ -z "$ipv4" ]; then
    ipv4="none"
  fi
  bus="n/a"
  if [ -e "$path/device" ]; then
    devlink="$(readlink -f "$path/device" 2>/dev/null || true)"
    case "$devlink" in
      *usb*) bus="usb" ;;
      *pci*) bus="pci" ;;
      *) bus="other" ;;
    esac
  fi
  line="  ${name}: state=${oper} carrier=${carrier} bus=${bus} mac=${mac} ipv4=${ipv4}"
  is_wifi=0
  if [ -d "$path/wireless" ] || [ -e "$path/phy80211" ]; then
    is_wifi=1
  fi
  if [ "$is_wifi" -eq 1 ]; then
    WIFI_DETAILS="${WIFI_DETAILS}${line}"$'\n'
  elif [ -e "$path/device" ] && [ "$iftype" = "1" ]; then
    ETH_DETAILS="${ETH_DETAILS}${line}"$'\n'
  else
    OTHER_DETAILS="${OTHER_DETAILS}${line} type=${iftype}"$'\n'
  fi
done
shopt -u nullglob

WIFI_RFKILL=0
BT_RFKILL=0
if have rfkill; then
  if rfkill list wifi 2>/dev/null | grep -q ':'; then
    WIFI_RFKILL=1
  fi
  if rfkill list bluetooth 2>/dev/null | grep -q ':'; then
    BT_RFKILL=1
  fi
fi

if [ -n "$ETH_DETAILS" ]; then
  ETHERNET="AVAILABLE"
else
  ETHERNET="NOT FOUND"
fi

if [ -n "$WIFI_DETAILS" ] || [ "$WIFI_RFKILL" -eq 1 ]; then
  WIFI="AVAILABLE"
else
  WIFI="NOT FOUND"
fi

BT_SYSFS=0
if [ -d /sys/class/bluetooth ]; then
  bt_names="$(ls -1 /sys/class/bluetooth 2>/dev/null || true)"
  if [ -n "$bt_names" ]; then
    BT_SYSFS=1
  fi
fi

if [ "$BT_SYSFS" -eq 1 ] || [ "$BT_RFKILL" -eq 1 ]; then
  BLUETOOTH="AVAILABLE"
else
  BLUETOOTH="NOT FOUND"
fi

if have bluetoothctl; then
  BLUEZ="INSTALLED"
else
  BLUEZ="NOT INSTALLED"
fi

hr
printf '%s\n' "Jetson System Check"
hr
printf '\n'
printf 'OS: %s\n' "$OS_PRETTY"
printf 'JetPack package: %s\n' "$JETPACK_PKG"
printf 'L4T file: %s\n' "$L4T_RAW"
printf 'L4T version: %s\n' "$L4T_VERSION"
printf 'L4T package: %s\n' "$L4T_PKG"
printf 'JetPack estimate: %s\n' "$JETPACK_ESTIMATE"
printf 'Kernel: %s\n' "$KERNEL"
printf 'Architecture: %s\n' "$ARCH"
printf 'Python: %s\n' "$PYTHON"
printf 'Jetson model: %s\n' "$MODEL"
printf 'Hostname: %s\n' "$HOST_NAME"
printf 'RAM: %s\n' "$RAM_SUMMARY"
printf 'Disk Free: %s\n' "$DISK_FREE"
printf '\n'
printf 'Ethernet: %s\n' "$ETHERNET"
if [ -n "$ETH_DETAILS" ]; then
  printf '%s' "$ETH_DETAILS"
else
  printf '  no physical Ethernet interface found\n'
fi
printf '\n'
printf 'Wi-Fi: %s\n' "$WIFI"
if [ -n "$WIFI_DETAILS" ]; then
  printf '%s' "$WIFI_DETAILS"
elif [ "$WIFI_RFKILL" -eq 1 ]; then
  printf '  rfkill lists a Wi-Fi radio, but no wireless network interface was found\n'
else
  printf '  no Wi-Fi interface or rfkill Wi-Fi radio found\n'
fi
printf '\n'
printf 'Bluetooth software (bluez): %s\n' "$BLUEZ"
printf 'Bluetooth adapter: %s\n' "$BLUETOOTH"
if [ "$BLUETOOTH" = "NOT FOUND" ] && [ "$BLUEZ" = "NOT INSTALLED" ]; then
  printf '  bluez is not installed, and the kernel did not expose an hci or rfkill Bluetooth device\n'
fi
printf '\n'
printf 'IP addresses:\n'
if [ -n "$ETH_DETAILS$WIFI_DETAILS$OTHER_DETAILS" ]; then
  printf '%s' "$ETH_DETAILS$WIFI_DETAILS$OTHER_DETAILS"
else
  printf '  none\n'
fi
printf '\n'
printf '%s\n' "This script did not install software or change any settings."
hr
printf '%s\n' "DETAILED REPORT"
hr

printf '\n----- /etc/os-release -----\n'
if [ -r /etc/os-release ]; then
  cat /etc/os-release
else
  printf 'UNAVAILABLE\n'
fi

printf '\n----- uname -a -----\n'
uname -a 2>&1 || true

printf '\n----- python3 --version -----\n'
if have python3; then
  python3 --version 2>&1 || true
  command -v python3 2>&1 || true
else
  printf 'COMMAND NOT FOUND: python3\n'
fi

printf '\n----- Jetson model -----\n'
if [ -r /proc/device-tree/model ]; then
  tr -d '\0' < /proc/device-tree/model
  printf '\n'
else
  printf 'UNAVAILABLE\n'
fi

printf '\n----- /etc/nv_tegra_release -----\n'
if [ -r /etc/nv_tegra_release ]; then
  cat /etc/nv_tegra_release
else
  printf 'UNAVAILABLE\n'
fi

printf '\n----- nvidia-l4t-core -----\n'
if have dpkg-query; then
  dpkg-query -W -f='${Package} ${Version}\n' nvidia-l4t-core 2>&1 || true
  printf '\n----- nvidia-jetpack -----\n'
  dpkg-query -W -f='${Package} ${Version}\n' nvidia-jetpack 2>&1 || true
else
  printf 'COMMAND NOT FOUND: dpkg-query\n'
fi

printf '\n----- free -h -----\n'
if have free; then
  free -h 2>&1 || true
else
  printf 'COMMAND NOT FOUND: free\n'
fi

printf '\n----- df -h -----\n'
if have df; then
  df -h 2>&1 || true
else
  printf 'COMMAND NOT FOUND: df\n'
fi

printf '\n----- hostname -----\n'
hostname 2>&1 || true

printf '\n----- ip link -----\n'
run_capture ip link

printf '\n----- ip addr -----\n'
run_capture ip addr

printf '\n----- rfkill list -----\n'
run_capture rfkill list

printf '\n----- bluetoothctl show -----\n'
run_capture bluetoothctl show

printf '\n----- lsusb -----\n'
run_capture lsusb

printf '\n----- /sys/class/bluetooth -----\n'
if [ -d /sys/class/bluetooth ]; then
  ls -1 /sys/class/bluetooth 2>&1 || true
else
  printf 'DIRECTORY NOT PRESENT\n'
fi

hr
printf '%s\n' "END OF SYSTEM CHECK"
printf '%s\n' "Copy this entire output back."
printf '%s\n' "This script did not change the system."
hr
