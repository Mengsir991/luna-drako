# luna-drako

Downshift (slow-motion DPI drop) fix for the **Lunafury Fury33 EVO** (TYPE33_54H — PixArt PAW3950
sensor, Nordic nRF54H20, official firmware `TYPE33_Mouse_54H20_App_v0.0.1.48_20261013`).

This is a **port of the AB downshift patch** from
[hyperdrako](https://gitlab.jaceee.dev/open/hyperdrako) (CRDRAKO KO-ONE) to the Lunafury TYPE33 EVO.
Both mice come from the same ODM platform (same VID `0x373E`, same image base `0x0E067000`,
77.7% string overlap) but are **two independent builds**, so hyperdrako's hardcoded addresses
cannot be reused directly — every patch site was re-derived on the Luna image and verified.

Unofficial and unaffiliated with Lunafury, CRDRAKO, PixArt or Nordic. Flashing firmware can brick
a device and may void your warranty. You do this at your own risk. The receiver (dongle) firmware
is never modified.

## What the patch changes

Stock firmware lowers the sensor resolution while the mouse moves slowly (slow aiming feels
"stuck", then jumps). The patch pins the resolution registers to their full-speed value in all
sensor scripts, exactly like hyperdrako profile AB does on the KO-ONE:

- **28 edit sites, 38 bytes changed** out of a 150 KB image — nothing else is touched
- every site is a `movs r1, #imm` (or register-alias equivalent) feeding the sensor
  register-write helper at `0x0E06B19C`
- see [`patch_spec_LUNA_A.json`](patch_spec_LUNA_A.json) for the complete list with expected
  old bytes (a mismatch aborts before anything is written)

Flash layout, firmware size and instruction count are unchanged; the patched image was verified
instruction-by-instruction with capstone before flashing, and byte-read-back after flashing.

## Requirements

- Python 3.9+ with `capstone`, `unicorn`, `hidapi` (`pip install capstone unicorn hidapi`)
- Windows / Linux / macOS (HID backend is from hyperdrako's `ko1_hid.py`)
- Close the Lunafury web driver before flashing (it holds the HID interface)

## Quick start

```bash
cd tools

# 0) sanity: mouse visible, firmware version should read 0.0.1.48
python luna_flash.py list
python luna_flash.py info

# 1) full backup of YOUR device (151552 bytes, ~2 min)  -- keep it safe!
python dump2.py 0x25000 device_full.bin

# 2) fetch the official stock image (.xvi is plain Intel HEX)
python fetch_stock.py

# 3) build the patched image from YOUR backup + the patch spec
python build_flash_image.py

# 4) dry-run, then flash (erase -> program -> verify, ~3-5 min, don't unplug)
python flash_write.py flash_patched.bin          # dry run
python flash_write.py flash_patched.bin --apply  # real flash

# 5) rollback anytime
python flash_write.py device_full.bin --apply
```

`build_flash_image.py` asserts that every expected old byte matches your device dump before
building, so it is safe to run even if your unit differs slightly.

## Sensor framerate profiles (new)

Following the downshift port, the sensor **framerate** scripts were patched too. Stock Luna
firmware runs the PAW3950 with a floating frame time (rest-mode ~150 µs ≈ 6.7 kfps up to
50 µs = 20 kfps while sweeping). Three firmware variants are supported:

| variant | HyperMode ON | HyperMode OFF | spec |
|---|---|---|---|
| `FPS20K` | locked 20 kfps | locked 20 kfps | [`patch_spec_LUNA_FPS20K.json`](patch_spec_LUNA_FPS20K.json) |
| `HYBRID` | locked 20 kfps | stock adaptive (power saving) | same spec, only the 3 `B(Hyper)` sites |
| `STOCK-FPS` | stock | stock | no framerate edits |

The recipe (from hyperdrako's `debounce_patch.py` notes, re-derived for the Luna image):
`07:0x42=0x14` (25 µs frame unit) + `06:0x53=0x02` + `06:0x62=0x02` fixes the frame time at
50 µs = **20000 fps**; `06:0x6D/0x6E` restore the rest-mode thresholds. 18 edit sites
(3 in the HyperMode script `B`, 5 in each of the three HyperMode-off script copies
`copy2a/2b/2c` — wired / dongle / BT branches), all `movs r1, #imm` form.

```bash
cd tools
# build the FPS20K image from your dump, flash, verify (18/18 + 28/28 read-back)
python check_fps.py      # after flashing flash_fps.bin
python check_hybrid.py   # after flashing flash_hybrid.bin (3 locked + 15 stock)
python switch_fw.py hybrid   # one-command switcher: hybrid | fps | stock
```

`switch.bat` is a double-clickable Windows wrapper (picks the bundled Python, shows a menu).

## App-mode config protocol (cls 1, unrelated to the bootloader)

- `0x00` set polling rate / `0x80` read — encoding `1`=1000 Hz, `32`=2000, `64`=4000, `128`=8000
- `0x0B` set HyperMode / `0x8B` read — `tools/hyper.py` and `tools/setrate.py` wrap these
- works over wired (`PID 0x0054`) and the 8 K receiver (`PID 0x0084`), always via `MI_02`

## How the port was derived

The KO-ONE patch addresses don't exist in the Luna image (same-address byte identity is only
6.6% — random). The port re-derives them semantically:

1. **`analysis/scan_script.py`** — scan both images for the sensor-script calling shape
   (`movs val / movs reg / bl helper`). Both firmwares have exactly 7 script regions calling
   one helper: KO-ONE `0x0E06BDB8`, Luna `0x0E06B19C`.
2. **`analysis/extract_writes.py`** — dump all 761/739 (reg, val) write sites from both.
3. **`analysis/map2.py`** — global sequence alignment (difflib, 96.8% coverage) maps all 28
   KO-ONE patch sites onto Luna addresses; every Luna site has the same instruction form.
4. **`analysis/check_r4b.py`** — verify the `r4 == 0` precondition at the six register-alias
   (P2) sites inside each containing function.
5. **`analysis/gen_patch.py`** — emit `patch_spec_LUNA_A.json`.
6. **`tools/final_check.py`** — disassemble the patched image and confirm 28/28 sites
   changed and nothing else moved.

## Bootloader protocol notes (nRF54H20, VID 0x373E)

| mode | PID | interface |
|---|---|---|
| app | `0x0054` | `MI_02` answers 64-byte feature reports (usage `0xFFFF`) |
| bootloader | `0xB054` | single interface |

- 64-byte HID feature reports, replies shifted by 1 byte, status `0xA1`
- app: cmd `0x81` = version query (replies `0.0.1.48`)
- enter bootloader: cls `0x00` cmd `0x00` arg `0xB0` (device resets, bootloader has an idle
  timeout and returns to the app on its own)
- bootloader: cls `0xB0` — cmd `0x80` version, `0x83` read 32 B (payload XOR `0x55`),
  erase + program + verify see `tools/flash_write.py`
- image base `0x0E067000`, image size `0x25000`

## Credits

- [hyperdrako](https://gitlab.jaceee.dev/open/hyperdrako) — the original KO-ONE patch set,
  flasher and HID layer this port builds on.
- Official stock image served from `mouse.lunafury.games` (URL in `tools/fetch_stock.py`);
  firmware binaries are intentionally **not** committed to this repository.

## Files

```
patch_spec_LUNA_A.json       28-site downshift patch table
patch_spec_LUNA_FPS20K.json  18-site 20 kfps framerate patch table
tools/                       flash, dump, build, verify, HyperMode/rate, switcher utilities
analysis/                    how the patch specs were derived from hyperdrako's
```
