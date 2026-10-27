#!/usr/bin/env python3
"""apply_patch.py -- stock hex + patch spec -> patched hex (layout preserving).

Only the Intel-HEX data records that actually contain patched bytes are re-emitted;
every other line is copied through byte-for-byte, so a text diff against the stock
file shows exactly the edited lines and nothing else.

Usage: apply_patch.py <stock.hex> <patch_spec.json> <out.hex>
"""
import sys, json, hashlib, re

REC = re.compile(rb'^:([0-9A-Fa-f]{2})([0-9A-Fa-f]{4})([0-9A-Fa-f]{2})((?:[0-9A-Fa-f]{2})*)([0-9A-Fa-f]{2})$')

def checksum(count, addr, rtype, data):
    s = (count + (addr >> 8 & 0xFF) + (addr & 0xFF) + rtype + sum(data)) & 0xFF
    return (-s) & 0xFF

def split_lines(blob):
    """Keep each line's exact terminator so layout is preserved."""
    out = []
    i = 0
    while i < len(blob):
        j = blob.find(b'\n', i)
        if j < 0:
            out.append((blob[i:], b'')); break
        line = blob[i:j+1]
        body = line.rstrip(b'\r\n')
        out.append((body, line[len(body):]))
        i = j + 1
    return out

def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    stock_path, spec_path, out_path = sys.argv[1:4]
    blob = open(stock_path, 'rb').read()
    spec = json.load(open(spec_path))

    got = hashlib.sha256(blob).hexdigest()
    if spec.get('stock_sha256') and got != spec['stock_sha256']:
        sys.exit('FATAL: stock hex sha256 mismatch\n  expected %s\n  got      %s'
                 % (spec['stock_sha256'], got))

    edits = {}
    for e in spec['edits']:
        a = int(e['address'], 16)
        old = bytes.fromhex(e['expected_old_bytes'])
        new = bytes.fromhex(e['new_bytes'])
        if len(old) != len(new):
            sys.exit('FATAL: edit at %s changes size (%d -> %d); in-place only'
                     % (e['address'], len(old), len(new)))
        for k in range(len(old)):
            if a + k in edits:
                sys.exit('FATAL: overlapping edits at 0x%08X' % (a + k))
            edits[a + k] = (old[k], new[k])

    lines = split_lines(blob)
    upper = 0
    out = []
    applied = set()
    touched_lines = 0
    for body, term in lines:
        m = REC.match(body)
        if not m:
            out.append(body + term); continue
        count = int(m.group(1), 16); addr = int(m.group(2), 16)
        rtype = int(m.group(3), 16); data = bytearray(bytes.fromhex(m.group(4).decode()))
        if rtype == 4:
            upper = int.from_bytes(bytes.fromhex(m.group(4).decode()), 'big')
            out.append(body + term); continue
        if rtype != 0:
            out.append(body + term); continue
        base = (upper << 16) | addr
        hits = [(k, base + k) for k in range(count) if base + k in edits]
        if not hits:
            out.append(body + term); continue
        for k, a in hits:
            exp, new = edits[a]
            if data[k] != exp:
                sys.exit('FATAL: expected_old_bytes mismatch at 0x%08X: file has 0x%02X, spec says 0x%02X'
                         % (a, data[k], exp))
            data[k] = new
            applied.add(a)
        # re-emit with the template's exact geometry; only the data+checksum change
        was_upper = m.group(4) == m.group(4).upper()
        hexdata = bytes(data).hex()
        hexdata = hexdata.upper() if was_upper else hexdata
        cs = checksum(count, addr, rtype, data)
        newbody = (':%02X%04X%02X%s%02X' % (count, addr, rtype, hexdata, cs)).encode()
        if not was_upper:
            newbody = (':%02x%04x%02x%s%02x' % (count, addr, rtype, hexdata, cs)).encode()
        out.append(newbody + term)
        touched_lines += 1

    missing = set(edits) - applied
    if missing:
        sys.exit('FATAL: %d spec byte(s) not found in any data record: %s'
                 % (len(missing), ', '.join('0x%08X' % a for a in sorted(missing))))

    blob_out = b''.join(out)
    open(out_path, 'wb').write(blob_out)
    print('profile %s: applied %d edits (%d bytes) across %d record line(s)'
          % (spec['profile'], len(spec['edits']), len(edits), touched_lines))
    print('  in  %s  sha256 %s' % (stock_path, got))
    print('  out %s  sha256 %s' % (out_path, hashlib.sha256(blob_out).hexdigest()))
    print('  size %d -> %d bytes (%s)'
          % (len(blob), len(blob_out), 'identical' if len(blob) == len(blob_out) else 'CHANGED'))

if __name__ == '__main__':
    main()
