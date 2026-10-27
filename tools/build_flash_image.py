import json, hashlib, sys
BASE=0x0E067000
dev=bytearray(open('device_full.bin','rb').read())
import os
SPEC=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','patch_spec_LUNA_A.json')
spec=json.load(open(SPEC))
applied=0
for e in spec['edits']:
    off=int(e['address'],16)-BASE
    old=bytes.fromhex(e['expected_old_bytes']); new=bytes.fromhex(e['new_bytes'])
    assert len(old)==len(new)
    got=bytes(dev[off:off+len(old)])
    assert got==old, f'实机底片字节不符 @{e["address"]}: 期望 {old.hex()} 实为 {got.hex()}'
    dev[off:off+len(new)]=new
    applied+=1
open('flash_patched.bin','wb').write(bytes(dev))
n=sum(1 for i in range(min(len(dev),151552)) if open('device_full.bin','rb').read()[i]!=dev[i])
print(f'以实机备份为底片, 应用 {applied} 处编辑')
print(f'  device_full.bin    sha256 {hashlib.sha256(open("device_full.bin","rb").read()).hexdigest()}')
print(f'  flash_patched.bin  sha256 {hashlib.sha256(bytes(dev)).hexdigest()}')
print(f'  与底片不同字节: {n} (应为 38)')
# 与官方镜像对照, 确认差异只有 38 + 11 padding
sys.path.insert(0,'.')
from hexlib import load_segments
def flat(p):
    segs=load_segments(p); lo=min(s for s,_ in segs); hi=max(s+len(b)-1 for s,b in segs)
    b=bytearray(b'\xFF'*(hi-lo+1))
    for s,x in segs: b[s-lo:s-lo+len(x)]=x
    return bytes(b)
off=flat('TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi')
m=min(len(off),len(dev))
d=[i for i in range(m) if off[i]!=dev[i]]
print(f'  与官方镜像不同字节: {len(d)} (11 padding + 38 patch = 49 预期)')
