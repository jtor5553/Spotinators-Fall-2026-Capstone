# Unitree R3-1 remote → Jetson Bluetooth (agent handoff)

Use this to make the **Unitree R3** (product name R3-1) drive Spot + the cone motor on the Jetson Orin Nano in `spot_cone_controller`. Lab config uses `controller.type: unitree_r3` (this is the primary Jetson pad).

Verified on lab Jetson `asl-lab-desktop` (L4T / tegra 5.15), 2026-10-27.

---

## 1. Device identity (this lab remote)

| Field | Value |
| --- | --- |
| Product | Unitree R3 / R3-1 handheld remote |
| Bluetooth name | `Unitree-34M54J` (always `Unitree-` + suffix; **not** advertised as `r3-1`) |
| MAC | `98:DA:10:03:37:BA` (public) |
| Adapter on Jetson | `hci0` Realtek USB (`13d3:3549` / IMC Networks), BD `F8:3D:C6:57:07:FE` |
| Pairing PIN that worked | `1234` |
| Transport that works | **Classic RFCOMM Serial Port (SPP), channel 1** |
| BLE GATT | Documented for phone/app (`FFE0`/`FFE1`/`FFE2`, handshake ASCII hex `59532b32` = `"YS+2"`). **Do not rely on BLE on this Jetson** — kernel has `# CONFIG_BT_LE is not set` |

Discover other remotes: `bluetoothctl devices \| grep Unitree`

---

## 2. Why GNOME / `bluetoothctl connect` fails alone

1. Dual-mode device. BlueZ `Device1.Connect()` prefers classic, then fails with:
   - `org.bluez.Error.NotAvailable br-connection-profile-unavailable`
2. ACL comes up briefly (`Connected: yes`) then drops unless something owns the **Serial Port** profile (`00001101-0000-1000-8000-00805f9b34fb`).
3. GNOME Settings cycling discovery / DualSense reconnect spam can also block scans (`InProgress` / busy).

**Fix:** keep device **Paired + Trusted**, and either:

- run a small daemon that registers a BlueZ SPP client profile with `AutoConnect=true` and/or holds an RFCOMM socket, or  
- open RFCOMM channel 1 from the Spot app itself and keep the socket open while controlling.

Already paired/trusted on this Jetson. Confirm:

```bash
bluetoothctl info 98:DA:10:03:37:BA
# expect: Paired: yes, Trusted: yes
```

---

## 3. Lab helper already running (optional dependency)

Files on the Jetson (outside the repo today):

| Path | Role |
| --- | --- |
| `/home/asl_lab/Desktop/TestingMotors/unitree_bt_daemon.py` | Registers SPP AutoConnect + PIN agent + reconnect watchdog |
| `/home/asl_lab/.config/systemd/user/unitree-bt.service` | User service, enabled at login |
| `/home/asl_lab/Desktop/TestingMotors/unitree_bt_force.py` | One-shot pair/trust/hold (manual) |

```bash
systemctl --user status unitree-bt
systemctl --user restart unitree-bt
```

**Preferred for Spotinator:** implement RFCOMM read **inside** `spot_cone_controller` so control does not depend on the TestingMotors daemon. If both open RFCOMM, one will get `Errno 16 Device or resource busy` — stop `unitree-bt` while testing the app reader:

```bash
systemctl --user stop unitree-bt
```

---

## 4. How to connect and read sticks (working recipe)

```python
import socket, struct

MAC = "98:DA:10:03:37:BA"  # or env UNITREE_MAC
CHANNEL = 1

sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
sock.settimeout(10)
sock.connect((MAC, CHANNEL))
sock.settimeout(1.0)

def read_frame(sock):
    buf = b""
    while len(buf) < 20:
        chunk = sock.recv(64)
        if not chunk:
            raise ConnectionError("RFCOMM closed")
        buf += chunk
    # if stream drifts, resync on 20-byte cadence; lab stream was aligned
    pkt, rest = buf[:20], buf[20:]
    lx, rx, ry, ly = struct.unpack("<ffff", pkt[:16])  # IEEE754 LE, ~[-1, 1]
    b1, b2, battery, rssi = pkt[16], pkt[17], pkt[18], pkt[19]
    return {
        "lx": lx, "ly": ly, "rx": rx, "ry": ry,
        "buttons1": b1, "buttons2": b2,
        "battery": battery, "rssi": rssi,
        "raw": pkt,
    }
```

Verified idle packet (sticks centered):

```text
000000800000008000000080000000000000423e
→ lx=ly=rx=ry≈0, battery=66, rssi=62
```

Rate is ~tens of Hz (same order as Unitree BLE docs ~20 Hz).

### Button bits (from Unitree BLE remote docs; same 20-byte layout on RFCOMM)

**Byte 16**

| Bit | Button |
| --- | --- |
| 0 | R1 |
| 1 | L1 |
| 2 | Start |
| 3 | Select |
| 4 | R2 |
| 5 | L2 |
| 6 | F1 |
| 7 | F2 |

**Byte 17**

| Bit | Button |
| --- | --- |
| 0 | A |
| 1 | B |
| 2 | X |
| 3 | Y |
| 4 | Up |
| 5 | Right |
| 6 | Down |
| 7 | Left |

```python
pressed = bool((byte >> bit) & 1)
```

R2 on this remote is a **digital bit**, not an analog trigger. For `ControllerState.r2`, map `1.0` / `0.0` from bit 4 of byte 16 (or treat L2/R2 as hold flags).

---

## 5. Pair / trust once (if MAC changes or bond wiped)

PIN agent must run on a GLib main loop or Pair times out with `NoReply`.

```bash
# high level
bluetoothctl trust 98:DA:10:03:37:BA
# pair with PIN 1234 via agent (see unitree_bt_force.py), then:
bluetoothctl info 98:DA:10:03:37:BA   # Paired yes, Trusted yes
```

Env overrides used by helpers: `UNITREE_MAC`, `UNITREE_PIN` (default `1234`).

**Do not confuse** with Unitree **robot bind ID** (6-digit sticker / App → Remote Binding → hold SELECT 3s). That binds R3 ↔ robot radio link, not Jetson BlueZ.

---

## 6. Integration in Spotinators repo (implemented)

`spot_cone_controller` can own the RFCOMM socket and drive Spot + the cone motor from the same `ControllerState` path as DualSense.

| Piece | Path / setting |
| --- | --- |
| Reader | `spot_cone_controller/controller/unitree_r3.py` |
| Selection | `controller.type: unitree_r3` in `config/config.yaml` (lab default) |
| MAC / channel | `controller.mac`, `controller.rfcomm_channel` (or env `UNITREE_MAC`) |
| Shared state | `controller/controller_state.py` — `left` / `right` / `r2` / buttons |

| R3 | ControllerState | App effect |
| --- | --- | --- |
| `lx`, `ly` | `left` | Walk |
| `rx`, `ry` | `right` | Yaw (`right.x`) |
| R2 bit | `r2` 0.0/1.0 | Boost |
| A | `buttons["x"]` | Hold ~0.5 s → drop cone |
| B / Y | `circle` / `triangle` | Display only |
| L1 / R1 | `lb` / `rb` | Sit / Stand |
| Start | `options` | Stop |

**Before starting the app with `type: unitree_r3`**, stop the lab helper so RFCOMM is free:

```bash
systemctl --user stop unitree-bt
bluetoothctl info 98:DA:10:03:37:BA   # Paired: yes, Trusted: yes
```

If both the daemon and the app open channel 1, one gets `Errno 16 Device or resource busy`. Restart the helper only when the Spot app is not reading the remote:

```bash
systemctl --user start unitree-bt
```

Deadzone uses `controller.deadzone` (default 0.12). On socket death the reader clears axes and sets `connected=False` so the existing pad-loss stop path runs. Reconnect uses backoff.

Optional later: copy the TestingMotors daemon into `spot_cone_controller/scripts/` if you want Settings-level Connected without the app holding RFCOMM.

---

## 7. Jetson / BlueZ gotchas

- Stock `bluetoothctl connect` / GNOME will look connected then drop without SPP owner.
- Discovery list in Settings is temporary; unpaired devices vanish when scan stops.
- NVIDIA `bluetooth.service` drop-in runs:  
  `bluetoothd -d --noplugin=audio,a2dp,avrcp` (audio plugins off — fine for this remote).
- Both `rtk_btusb` and `btusb` modules present; device bound to `rtk_btusb`.
- `CONFIG_BT_LE` disabled → BLE/`gatttool` path is not the integration strategy here.
- User is not in `dialout`; Python `AF_BLUETOOTH` RFCOMM works without `/dev/rfcomm0`.

---

## 8. Quick validation checklist

```bash
bluetoothctl info 98:DA:10:03:37:BA   # Paired+Trusted
systemctl --user stop unitree-bt      # if app will open RFCOMM
python3 -c "
import socket,struct
s=socket.socket(socket.AF_BLUETOOTH,socket.SOCK_STREAM,socket.BTPROTO_RFCOMM)
s.connect(('98:DA:10:03:37:BA',1))
p=s.recv(20)
print(struct.unpack('<ffff',p[:16]), p[16:].hex())
"
# move sticks → floats leave 0; press A → bit0 of byte17
```

Then: Spot walk in mock/disarmed → map sticks → enable motor/dispenser only with existing safety arming.

---

## 9. Reference links used in lab debug

- Unitree remote BLE layout / handshake: https://github.com/legion1581/unitree_ui/blob/main/docs/remote-control.md  
  (RFCOMM on this Jetson carried the same 20-byte stick/button payload without needing the BLE handshake.)
- Official R3 ↔ robot bind (App + 6-digit ID + SELECT): Unitree support “Remote Control” docs — separate from Jetson pairing.
