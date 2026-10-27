#!/usr/bin/env python3
"""
luna_flash.py - tool for the Lunafury TYPE33 EVO (nRF54H20, PID 373E:0054).

Protocol inherited from hyperdrako's ko1_flash.py (CRDRAKO KO-ONE) and
CONFIRMED on this unit: cmd 0x81 returns status 0xA1 and firmware version
0.0.1.48, matching the official image name.

Commands:
  list                  enumerate every HID interface with VID 373E
  info                  firmware version (read-only)
  enter-bl / exit-bl    jump to / leave the bootloader
  dump -o OUT.xvi       read the whole image back (read-only)
  flash FILE.xvi        write (gated, needs --allow-write + --i-understand)
"""
import argparse, re, sys, time

VID        = 0x373E
APP_PID    = 0x0054      # mouse   (panel: TYPE33_54H / PIDWired)
BL_PID     = 0xB054      # mouse bootloader (DeviceBLPID)
RX_PID     = 0x0084      # 8K receiver
RX_BL_PID  = 0xB084      # 8K receiver bootloader
IMAGE_BASE = 0x0E067000
IMAGE_SIZE = 0x24A00     # 150 kB, matches the official image
XOR        = 0x55
CLS_BL     = 0xB0
STATUS_OK  = (0xA1, 0x02)

import ko1_hid
from ko1_hid import HidOpenError, find_nodes, wait_for_node


class ProtocolError(RuntimeError):
    pass


def pkt(target, length, cls, cmd, args=b""):
    p = bytearray(64)
    p[2], p[3], p[4], p[5] = target, length, cls, cmd
    p[6:6 + len(args)] = args
    return bytes(p)


class Link:
    def __init__(self, dev, target=0, delay=0.001):
        self.dev, self.target, self.delay = dev, target, delay
        self.off = None

    def get(self):
        raw = self.dev.get_report()
        if 0xA0 <= raw[0] <= 0xAF:
            self.off = 0
        elif 0xA0 <= raw[1] <= 0xAF:
            self.off = 1
        return raw[self.off or 0:]

    def request(self, p, tries=500, poll=30, poll_gap=0.002):
        for _ in range(tries):
            self.dev.set_report(p)
            time.sleep(self.delay)
            n = self.get()
            if n[0] in STATUS_OK and n[4] == CLS_BL:
                return n
            if n[0] < 0xA1:
                for _ in range(poll):
                    time.sleep(poll_gap)
                    n = self.get()
                    if n[0] in STATUS_OK and n[4] == CLS_BL:
                        return n
        raise ProtocolError("device never acknowledged - protocol may differ")

    def app_version(self):
        self.dev.set_report(pkt(self.target, 16, 0, 0x81))
        time.sleep(0.15)
        n = self.get()
        if n[0] in STATUS_OK and n[5] == 0x81:
            return ".".join(str(b) for b in n[6:10])
        return None

    def bl_version(self):
        self.dev.set_report(pkt(self.target, 6, CLS_BL, 0x80))
        time.sleep(0.15)
        n = self.get()
        if n[0] in STATUS_OK:
            return f"{n[8]:x}.{n[9]:02x}.{n[10]:02x}.{n[11]:02x}"
        return None

    def read_chunk(self, addr, size=32):
        p = pkt(self.target, size, CLS_BL, 0x83, bytes([size]) + addr.to_bytes(4, "big"))
        n = self.request(p)
        return bytes(b ^ XOR for b in n[11:11 + size])

    def enter_bl(self):
        try:
            self.dev.set_report(pkt(self.target, 1, 0, 0, bytes([CLS_BL])))
        except OSError as e:
            print(f"  (device reset during command: {e}; expected)")

    def exit_bl(self):
        try:
            self.dev.set_report(pkt(self.target, 1, CLS_BL, 4, bytes([CLS_BL])))
        except OSError as e:
            print(f"  (device reset during command: {e}; expected)")


def pid_of(node):
    m = re.search(r'PID_([0-9A-Fa-f]{4})', str(node.path))
    return int(m.group(1), 16) if m else 0


def nodes_for(vid, pid):
    return [n for n in find_nodes(vid, 0) if pid_of(n) == pid]


def pick_config(vid, pid, override=None):
    """Return the interface that actually answers a 64-byte feature report."""
    if override:
        return ko1_hid.backend().node_from_path(override)
    nodes = nodes_for(vid, pid)
    if not nodes:
        raise HidOpenError(f"no HID interface {vid:04X}:{pid:04X} - plugged in? panel closed?")
    nodes.sort(key=lambda n: (0 if "MI_02" in str(n.path) else
                              1 if n.usage_page in (0xffff, 0xffa0) else 2, n.path))
    for n in nodes:
        try:
            dev = ko1_hid.open_node(n)
        except Exception:
            continue
        try:
            dev.set_report(pkt(0, 16, 0, 0x81))
            time.sleep(0.15)
            raw = dev.get_report()
            if raw[0] in STATUS_OK or raw[1] in STATUS_OK:
                return n
        except Exception:
            pass
        finally:
            dev.close()
    raise HidOpenError("no interface answered the version query")


def cmd_list(a):
    nodes = find_nodes(VID, 0)
    if not nodes:
        print(f"no HID interface with VID {VID:04X}")
        return
    for n in nodes:
        pid = pid_of(n)
        tag = ("  <== EVO mouse app" if pid == APP_PID else
               "  <== EVO mouse BOOTLOADER" if pid == BL_PID else
               "  <== 8K receiver" if pid == RX_PID else
               "  <== 8K receiver BOOTLOADER" if pid == RX_BL_PID else "")
        print(f"  {n.describe()}{tag}")


def cmd_info(a):
    node = pick_config(VID, APP_PID, a.node)
    dev = ko1_hid.open_node(node)
    try:
        v = Link(dev).app_version()
        print(f"  firmware version: {v}" if v else "  no reply")
    finally:
        dev.close()


def cmd_enter_bl(a):
    dev = ko1_hid.open_node(pick_config(VID, APP_PID, a.node))
    try:
        Link(dev).enter_bl()
        print("  jumping to bootloader... then: luna_flash.py dump -o backup.xvi")
    finally:
        dev.close()


def cmd_exit_bl(a):
    dev = ko1_hid.open_node(pick_config(VID, BL_PID, a.node))
    try:
        Link(dev).exit_bl()
        print("  leaving bootloader...")
    finally:
        dev.close()


def cmd_dump(a):
    wait_for_node(VID, BL_PID, 20, "bootloader")
    node = pick_config(VID, BL_PID, a.node)
    dev = ko1_hid.open_node(node)
    try:
        link = Link(dev)
        v = link.bl_version()
        print(f"  bootloader version: {v}" if v else "  (no bootloader version)")
        size, out, t0 = a.size, bytearray(), time.time()
        for off in range(0, size, 32):
            out.extend(link.read_chunk(IMAGE_BASE + off))
            done = len(out)
            if done % (32 * 256) < 32:
                el = max(time.time() - t0, 1e-9)
                print(f"\r    {done}/{size}  ({100*done/size:5.1f}%)  {done/el/1024:6.1f} KB/s   ",
                      end="", flush=True)
        print(f"\r    {len(out)}/{size} bytes  (100.0%)                          ")
        with open(a.o, "w") as f:
            for i in range(0, len(out), 16):
                row = out[i:i + 16]
                line = bytearray([len(row), (i >> 8) & 0xFF, i & 0xFF, 0x00]) + row
                line.append((-sum(line)) & 0xFF)
                f.write(":" + line.hex().upper() + "\n")
            f.write(":00000001FF\n")
        print(f"  written {a.o}")
    finally:
        dev.close()


def cmd_backup(a):
    """enter-bl -> dump -> exit-bl in one go, so the mouse comes back online ASAP."""
    import os
    print("  entering bootloader (the mouse will stop moving for a few seconds)...")
    a2 = argparse.Namespace(node=a.node)
    cmd_enter_bl(a2)
    time.sleep(1.5)
    try:
        cmd_dump(argparse.Namespace(o=a.o, size=a.size, node=a.node))
    finally:
        time.sleep(0.5)
        print("  restoring normal operation...")
        try:
            wait_for_node(VID, BL_PID, 10, "bootloader")
        except Exception:
            pass
        try:
            cmd_exit_bl(argparse.Namespace(node=a.node))
        except Exception as e:
            print(f"  (could not send exit-bl: {e} - replug the cable to recover)")


def cmd_flash(a):
    print("write path is not enabled yet - the read path must be proven first.")
    print("Once `dump` produces a byte-exact match with the official image,")
    print("the write path (erase + program + verify) can be enabled safely.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("list", cmd_list), ("info", cmd_info),
                     ("enter-bl", cmd_enter_bl), ("exit-bl", cmd_exit_bl)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        p.add_argument("--node")
    p = sub.add_parser("dump"); p.add_argument("-o", required=True); p.add_argument("--node")
    p.add_argument("--size", type=lambda x: int(x, 0), default=IMAGE_SIZE)
    p.set_defaults(fn=cmd_dump)
    p = sub.add_parser("backup"); p.add_argument("-o", required=True); p.add_argument("--node")
    p.add_argument("--size", type=lambda x: int(x, 0), default=IMAGE_SIZE)
    p.set_defaults(fn=cmd_backup)
    p = sub.add_parser("flash"); p.add_argument("f"); p.set_defaults(fn=cmd_flash)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
