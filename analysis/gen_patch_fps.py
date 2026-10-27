"""Generate the fixed-20k frame-rate patch spec for the Lunafury TYPE33 EVO.

Recipe (from hyperdrako README_debounce / debounce_patch.py, PixArt mode C):
  07:42 unit = 0x14 (25 us), 06:53 longest = 0x02, 06:62 shortest = 0x02
  (fixed 50 us frame = 20k fps), 06:6D = 0x98, 06:6E = 0x80.
Applied to the Hyper (B) and Hyper-off (copy2-equivalent) scripts; the C/D
scripts already carry the fixed-20k values from the factory.
"""
import json, hashlib, re, sys
sys.path.insert(0,'.')
from hexlib import load_segments
LU='TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi'
def flat(p):
    segs=load_segments(p); lo=min(s for s,_ in segs); hi=max(s+len(b)-1 for s,b in segs)
    buf=bytearray(b'\xFF'*(hi-lo+1))
    for s,b in segs: buf[s-lo:s-lo+len(b)]=b
    return lo,bytes(buf)
LO,raw=flat(LU)
STOCK_SHA=hashlib.sha256(open(LU,'rb').read()).hexdigest()
BASE=0x0E067000
C20=dict(fps='20k', unit=0x14, fps_max=0x02, fps_min=0x02, unk1=0x98, unk2=0x80)

# (ins_a 地址, 寄存器, 原值, 新值, 模式名)
edits_raw=[]
def add(ins_a, reg, old, new, mode):
    edits_raw.append((ins_a, reg, old, new, mode))

# B 等效 (Hyper): 0x0E0835D4..0x0E083614
add(0x0E0835D4, 0x53, 0x03, C20['fps_max'], 'B(Hyper)')
add(0x0E0835F4, 0x6D, 0x8F, C20['unk1'],    'B(Hyper)')
add(0x0E0835FC, 0x6E, 0x70, C20['unk2'],    'B(Hyper)')
# copy2 等效 (Hyper off) x3
for base,tag in [(0x0E083F66,'copy2a'),(0x0E084266,'copy2b'),(0x0E08456A,'copy2c')]:
    add(base+0x00, 0x53, 0x03, C20['fps_max'], tag)
    add(base+0x08, 0x62, 0x01, C20['fps_min'], tag)
    add(base+0x20, 0x6D, 0x8F, C20['unk1'],    tag)
    add(base+0x28, 0x6E, 0x70, C20['unk2'],    tag)
    add(base+0x40, 0x42, 0x28, C20['unit'],    tag)

edits=[]
seen=set()
for ins_a, reg, old, new, mode in sorted(edits_raw):
    assert ins_a%2==0 and ins_a not in seen; seen.add(ins_a)
    got=raw[ins_a-LO]
    assert got==old, f'@{ins_a:#x} 期望 {old:#x} 实为 {got:#x}'
    assert raw[ins_a-LO+1]==0x21 and raw[ins_a-LO+2]==reg and raw[ins_a-LO+3]==0x20, \
        f'@{ins_a:#x} 指令形态不符: {raw[ins_a-LO:ins_a-LO+4].hex()}'
    edits.append(dict(prof='FPS20K', fn=mode, encoding='P1',
                      address=hex(ins_a), offset=ins_a-LO,
                      expected_old_bytes=f'{old:02x}', new_bytes=f'{new:02x}',
                      before=f'movs r1, #{old:#x}', after=f'movs r1, #{new:#x}',
                      sensor=f'page06/07 reg {reg:#04x} = {old:#04x} -> {new:#04x}'))
# 与 A 补丁不重叠
a_spec=json.load(open('patch_spec_LUNA_A.json'))
a_offs={e['offset']+k for e in a_spec['edits'] for k in range(len(bytes.fromhex(e['expected_old_bytes'])))}
for e in edits:
    assert e['offset'] not in a_offs, f"与 A 补丁重叠 @{e['address']}"
spec=dict(profile='FPS20K', device='Lunafury TYPE33 EVO (nRF54H20)',
          source_image=LU, image_base='0x0E067000', stock_sha256=STOCK_SHA,
          derived_from='hyperdrako debounce_patch.py FPS preset "20k" (fixed 50us frame)',
          recipe='07:42=0x14(25us) 06:53=0x02 06:62=0x02 (fixed 20k fps) 06:6D=0x98 06:6E=0x80',
          edit_count=len(edits), byte_count=len(edits), edits=edits)
json.dump(spec, open('patch_spec_LUNA_FPS20K.json','w'), indent=1, ensure_ascii=False)
print(f'生成 patch_spec_LUNA_FPS20K.json: {len(edits)} 处编辑')
for e in edits: print(f"  {e['fn']:>8} 0x{int(e['address'],16):08X}  {e['expected_old_bytes']} -> {e['new_bytes']}  {e['sensor']}")
