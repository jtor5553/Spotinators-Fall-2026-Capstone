#!/usr/bin/env bash
# Report Wi-Fi and, only with --apply, create an offline access point.
# This script does not assume a Wi-Fi radio exists.
# Example address only, and only when you pass it yourself:
#   bash scripts/setup_hotspot.sh --apply --interface wlan0 --address 192.168.50.1 --password 'choose-a-passphrase'

set -u

APPLY=0
IFACE=""
SSID="SPOT-CONE-CONTROL"
ADDRESS=""
PASSWORD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --interface)
      IFACE="${2:-}"
      shift
      ;;
    --ssid)
      SSID="${2:-}"
      shift
      ;;
    --address)
      ADDRESS="${2:-}"
      shift
      ;;
    --password)
      PASSWORD="${2:-}"
      shift
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1"
      exit 2
      ;;
  esac
  shift
done

found=""
shopt -s nullglob
for path in /sys/class/net/*; do
  name="${path##*/}"
  if [[ -d "$path/wireless" || -e "$path/phy80211" ]]; then
    found="${found} ${name}"
  fi
done
shopt -u nullglob

printf 'Jetson hotspot check\n'
if [[ -z "${found// /}" ]]; then
  printf 'Wi-Fi: NOT FOUND\n'
  printf 'No hotspot changes were made.\n'
  exit 0
fi

printf 'Wi-Fi: AVAILABLE\n'
printf 'Interfaces:%s\n' "$found"

if [[ "$APPLY" -eq 0 ]]; then
  printf 'No changes were made.\n'
  printf 'To configure an access point, pass --apply --interface <name> --address <ipv4>.\n'
  exit 0
fi

if [[ -z "$IFACE" || -z "$ADDRESS" || -z "$PASSWORD" ]]; then
  printf 'Refusing to apply: --interface, --address, and --password are required.\n'
  printf 'No changes were made.\n'
  exit 2
fi

if [[ "${#PASSWORD}" -lt 8 ]]; then
  printf 'Refusing to apply: the hotspot password must be at least 8 characters.\n'
  printf 'No changes were made.\n'
  exit 2
fi

case " ${found} " in
  *" ${IFACE} "*) ;;
  *)
    printf 'Refusing to apply: %s is not a detected Wi-Fi interface.\n' "$IFACE"
    printf 'No changes were made.\n'
    exit 2
    ;;
esac

if ! command -v nmcli >/dev/null 2>&1; then
  printf 'nmcli was not found. No changes were made.\n'
  exit 2
fi

if [[ "$(id -u)" -ne 0 ]]; then
  printf 'Root is required for --apply. No changes were made.\n'
  exit 2
fi

printf 'Creating offline access point %s on %s at %s\n' "$SSID" "$IFACE" "$ADDRESS"
nmcli device wifi hotspot ifname "$IFACE" con-name spot-cone-control ssid "$SSID" password "$PASSWORD"
nmcli connection modify spot-cone-control ipv4.method manual ipv4.addresses "${ADDRESS}/24" connection.autoconnect yes
nmcli connection up spot-cone-control
printf 'Hotspot requested. Confirm the address with: ip addr show %s\n' "$IFACE"
