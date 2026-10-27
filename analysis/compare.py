import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from hexlib import load_segments

import json

# inputs - adjust if your layout differs
STOCK = os.environ.get('STOCK', os.path.join('..', 'tools', 'TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi'))       # Luna official image
KO_HEX = os.environ.get('KO_HEX', os.environ.get('KO1_HEX', '54H_mouse_Cpurad_App_v01.09.02.05.hex'))  # hyperdrako stock hex
HYPERDRAKO_SPEC = os.environ.get('HYPERDRAKO_SPEC', 'patch_spec_A.json')  # hyperdrako out/patch_spec_A.json

import sys, json
sys.path.insert(0,'.')
from hexlib import load_segments

KO=KO_HEX
LU=STOCK

def flat(path):
    segs = load_segments(path)
    lo = min(s for s,_ in segs); hi = max(s+len(b)-1 for s,b in segs)
    buf = bytearray(b'\xFF'*(hi-lo+1))
    for s,b in segs:
        buf[s-lo:s-lo+len(b)] = b
    return lo, bytes(buf)

ko_lo, ko = flat(KO)
lu_lo, lu = flat(LU)
print(f'KO-ONE  0x{ko_lo:08X} size {len(ko)}')
print(f'LUNA    0x{lu_lo:08X} size {len(lu)}')
assert ko_lo == lu_lo, 'base differs'

# common address range actually written in both
n = min(len(ko), len(lu))
same = sum(1 for i in range(n) if ko[i]==lu[i])
print(f'\n== 前 {n} 字节重合区: 完全一致 {same} / {n} = {100*same/n:.2f}%')

# differing ranges (granularity 16 bytes)
runs=[]; start=None
for i in range(0,n,16):
    blk=min(16,n-i)
    diff = ko[i:i+blk]!=lu[i:i+blk]
    if diff and start is None: start=i
    elif not diff and start is not None:
        runs.append((start,i)); start=None
if start is not None: runs.append((start,n))
print(f'\n== 差异区块数: {len(runs)}')
tot=sum(b-a for a,b in runs)
print(f'== 差异总字节(±16粒度): {tot}')

print('\n== 主要差异区块（按大小, top 25）==')
for a,b in sorted(runs,key=lambda r:r[1]-r[0],reverse=True)[:25]:
    print(f'   0x{ko_lo+a:08X} .. 0x{ko_lo+b-1:08X}   {b-a:>6} bytes')

print('\n== 连续大段完全相同 (>=4096 byte gaps between diffs) ==')
g=[]; prev=n
for a,b in reversed(runs):
    if prev-a>=4096: g.append((ko_lo+a,ko_lo+prev,prev-a))
    prev=a
if prev>=4096: g.append((ko_lo,ko_lo+prev,prev))
print(f'   共 {len(g)} 段，最长:')
for addr,end,ln in sorted(g,key=lambda x:-x[2])[:6]:
    print(f'   0x{addr:08X} .. 0x{end-1:08X}  {ln:>7} bytes 完全一致')
