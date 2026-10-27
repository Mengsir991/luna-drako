import sys, json, hashlib, re
sys.path.insert(0,'.')
from hexlib import load_segments
rows=json.load(open('mapped2.json'))
LU='TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi'
def flat(p):
    segs=load_segments(p); lo=min(s for s,_ in segs); hi=max(s+len(b)-1 for s,b in segs)
    buf=bytearray(b'\xFF'*(hi-lo+1))
    for s,b in segs: buf[s-lo:s-lo+len(b)]=b
    return lo,bytes(buf)
LO,raw=flat(LU)
STOCK_SHA=hashlib.sha256(open(LU,'rb').read()).hexdigest()
edits=[]
for r in rows:
    if not r['ok']: raise SystemExit('存在未映射点，拒绝生成')
    enc=r['enc']; new=int(r['new'],16)
    if enc in ('P1','P3a'):
        addr=r['lu_addr']; old=raw[addr-LO:addr-LO+1]
        assert old[0]==(r['lu_val'] is not None and r['ko_val']) or True
        assert old[0]==r['ko_val'], f'imm 不符 @{addr:#x}: {old.hex()} vs {r["ko_val"]:#x}'
        assert addr%2==0
        edits.append(dict(prof='A',fn=r['fn'],encoding=enc,address=hex(addr),offset=addr-LO,
                          expected_old_bytes=old.hex(),new_bytes=('%02x'%new),
                          before=r['lu_a'],after=re.sub(r'#0x[0-9a-f]+',f'#0x{new:02x}',r['lu_a']),
                          sensor=f"reg {r['lu_reg'] if r['lu_reg'] is not None else old[0]:#04x} value {old[0]:#04x} -> {new:#04x}"))
    elif enc=='P3b':
        addr=r['lu_b']; old=raw[addr-LO:addr-LO+2]
        assert old.hex()=='0846', f'P3b 原字节异常 @{addr:#x}: {old.hex()}'
        edits.append(dict(prof='A',fn=r['fn'],encoding=enc,address=hex(addr),offset=addr-LO,
                          expected_old_bytes='0846',new_bytes='4f20',
                          before=r['lu_b2'],after='movs r0, #0x4f',
                          sensor='寄存器号改为显式立即数 0x4f'))
    elif enc=='P2':
        addr=r['lu_addr']; old=raw[addr-LO:addr-LO+2]
        assert old.hex()=='2146', f'P2 原字节异常 @{addr:#x}: {old.hex()}'
        edits.append(dict(prof='A',fn=r['fn'],encoding=enc,address=hex(addr),offset=addr-LO,
                          expected_old_bytes='2146',new_bytes='0221',
                          before=r['lu_a'],after='movs r1, #0x02',
                          sensor=f"reg {r['lu_reg']:#04x} value 0x00 -> 0x02 (原由 r4=0 提供)"))
    else: raise SystemExit('未知编码 '+enc)
# 重叠检查
seen={}
for e in edits:
    a=e['offset']
    for k in range(len(bytes.fromhex(e['expected_old_bytes']))):
        assert a+k not in seen, f'重叠 @{a+k:#x}'
        seen[a+k]=e
spec=dict(profile='A',device='Lunafury TYPE33 EVO (nRF54H20)',
          source_image=LU, image_base='0x0E067000', stock_sha256=STOCK_SHA,
          derived_from='hyperdrako patch_spec_A.json (CRDRAKO KO-ONE v01.09.02.05)',
          helper=dict(ko1='0x0E06BDB8', luna='0x0E06B19C'),
          edit_count=len(edits), byte_count=sum(len(bytes.fromhex(e['expected_old_bytes'])) for e in edits),
          edits=edits)
json.dump(spec, open('patch_spec_LUNA_A.json','w'), indent=1, ensure_ascii=False)
print(f'生成 patch_spec_LUNA_A.json: {len(edits)} 处编辑, {spec["byte_count"]} 字节')
print(f'stock sha256: {STOCK_SHA}')
print()
for e in edits: print(f"  {e['fn']:>6} {e['encoding']:>4} 0x{int(e['address'],16):08X}  {e['expected_old_bytes']} -> {e['new_bytes']:6s}  {e['sensor']}")
