import re
REC = re.compile(r'^:([0-9A-Fa-f]{2})([0-9A-Fa-f]{4})([0-9A-Fa-f]{2})((?:[0-9A-Fa-f]{2})*)([0-9A-Fa-f]{2})\s*$')

def load_segments(path):
    """Return list of contiguous (start_addr, bytes) segments, sorted."""
    pending = {}
    segs = []
    def flush():
        nonlocal pending
        if not pending:
            return
        addrs = sorted(pending)
        cur_s = None; buf = bytearray()
        for a in addrs:
            if cur_s is None:
                cur_s = a; buf = bytearray(pending[a]); prev = a; prevlen = len(pending[a])
                continue
            if a == prev + prevlen:
                buf.extend(pending[a]); prev = a; prevlen = len(pending[a])
            else:
                segs.append((cur_s, bytes(buf)))
                cur_s = a; buf = bytearray(pending[a]); prev = a; prevlen = len(pending[a])
        if cur_s is not None:
            segs.append((cur_s, bytes(buf)))
        pending = {}
    upper = 0
    for line in open(path, 'rb').read().decode('utf-8', 'replace').splitlines():
        m = REC.match(line.strip())
        if not m:
            continue
        cnt = int(m.group(1), 16); addr = int(m.group(2), 16)
        rtype = int(m.group(3), 16); data = bytes.fromhex(m.group(4))
        if len(data) != cnt:
            continue
        if rtype == 4:
            flush(); upper = int.from_bytes(data, 'big')
        elif rtype == 0:
            a = (upper << 16) | addr
            if a in pending:
                flush()
            pending[a] = data
    flush()
    segs.sort()
    return segs
