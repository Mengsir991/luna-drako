import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from hexlib import load_segments

import re, json, difflib
from capstone import *

# inputs - adjust if your layout differs
STOCK = os.environ.get('STOCK', os.path.join('..', 'tools', 'TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi'))       # Luna official image
KO_HEX = os.environ.get('KO_HEX', os.environ.get('KO1_HEX', '54H_mouse_Cpurad_App_v01.09.02.05.hex'))  # hyperdrako stock hex
HYPERDRAKO_SPEC = os.environ.get('HYPERDRAKO_SPEC', 'patch_spec_A.json')  # hyperdrako out/patch_spec_A.json

from capstone import *
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS); md.detail=False
KO=KO_HEX
LU=STOCK
IMM=re.compile(r'^\s*r(\d+),\s*#(0x[0-9a-f]+|\d+)$')
REG=re.compile(r'^\s*r(\d+),\s*r(\d+)$')
norm=lambda ins: re.sub(r'\br\d+\b','rN',f'{ins.mnemonic} {ins.op_str}')
def disasm(path):
    ins=[]
    for s,b in load_segments(path):
        off=0 if s%2==0 else 1
        ins.extend(list(md.disasm(b[off:], s+off)))
    ins.sort(key=lambda i:i.address); return ins
def writes(path, helper):
    ins=disasm(path); out=[]
    for i in range(len(ins)-2):
        a,b,c=ins[i],ins[i+1],ins[i+2]
        if c.mnemonic!='bl' or c.op_str!=helper: continue
        bimm=IMM.match(b.op_str)
        reg = int(bimm.group(2),0) if bimm else None
        aimm=IMM.match(a.op_str)
        val = int(aimm.group(2),0) if aimm else None
        out.append(dict(addr=c.address, ins_a=a.address, ins_b=b.address,
                        reg=reg, val=val, a=norm(a), b=norm(b), a_raw=f'{a.mnemonic} {a.op_str}',
                        b_raw=f'{b.mnemonic} {b.op_str}', bytes_a=a.bytes.hex(), bytes_b=b.bytes.hex(),
                        off_a=a.address-0x0E067000, off_b=b.address-0x0E067000))
    return out
ko=writes(KO,'#0xe06bdb8'); lu=writes(LU,'#0xe06b19c')
print(f'KO 写入点 {len(ko)}   LU 写入点 {len(lu)}')
sig=lambda ws:[(w['reg'],w['val'],w['a'],w['b']) for w in ws]
sm=difflib.SequenceMatcher(None, sig(ko), sig(lu), autojunk=False)
blocks=[b for b in sm.get_matching_blocks() if b.size>=1]
cov=sum(b.size for b in blocks)
print(f'全局对齐: {cov}/{len(ko)} KO 点已配对 ({100*cov/len(ko):.1f}%), 匹配块 {len(blocks)} 个')
# 构造 KO index -> LU index 映射
k2l={}
for a,b,size in blocks:
    for k in range(size): k2l[a+k]=b+k
# KO 指令地址 -> KO write index
idx_by_a={w['ins_a']:i for i,w in enumerate(ko)}
idx_by_b={w['ins_b']:i for i,w in enumerate(ko)}
spec=json.load(open(HYPERDRAKO_SPEC))
rows=[]
for e in spec['edits']:
    addr=int(e['address'],16)
    i=idx_by_a.get(addr)
    if i is None:
        # 可能落在第二条指令 (mov r0,r1 / movs r0,#reg)
        i=idx_by_b.get(addr)
    if i is None:
        for j,w in enumerate(ko):
            if w['ins_a']<=addr<=w['ins_b']: i=j; break
    if i is None: rows.append(dict(ok=False,ko_addr=addr,reason='KO 侧未落到写入点')); continue
    j=k2l.get(i)
    if j is None: rows.append(dict(ok=False,ko_addr=addr,reason='未对齐到 LUNA')); continue
    kw=ko[i]; lw=lu[j]
    rows.append(dict(ok=True, ko_addr=addr, ko_reg=kw['reg'], ko_val=kw['val'],
                     new=e['new_bytes'], enc=e['encoding'], fn=e['fn'],
                     sensor=e['sensor_effect'], lu_addr=lw['ins_a'], lu_b=lw['ins_b'],
                     lu_reg=lw['reg'], lu_val=lw['val'], lu_a=lw['a_raw'], lu_b2=lw['b_raw'],
                     lu_bytes_a=lw['bytes_a'], lu_bytes_b=lw['bytes_b'],
                     lu_off_a=lw['off_a'], lu_off_b=lw['off_b']))
good=[r for r in rows if r['ok']]
print(f'补丁点映射成功 {len(good)}/{len(rows)}\n')
print(f"{'fn':>6} {'KO地址':>12} {'reg':>5} {'旧值':>5} {'新值':>6} {'编码':>4} | {'LUNA地址':>12} {'reg':>5} {'旧值':>5} {'形态(a|b)':>28}")
print('-'*112)
def fmt(v, spec_='>#5x'):
    return format(v, spec_) if v is not None else ' None'
for r in good:
    flag='' if (r['lu_reg']==r['ko_reg'] and r['lu_val']==r['ko_val']) else '  <<< 核对'
    print(f"{r['fn']:>6} 0x{r['ko_addr']:08X} {fmt(r['ko_reg'])} {fmt(r['ko_val'])} {int(r['new'],16):>#6x} {r['enc']:>4} | 0x{r['lu_addr']:08X} {fmt(r['lu_reg'])} {fmt(r['lu_val'])} {(r['lu_a']+' | '+r['lu_b2']):>30}{flag}")
for r in rows:
    if not r['ok']: print(f"  ✗ KO 0x{r['ko_addr']:08X}: {r['reason']}")
json.dump(rows, open('mapped2.json','w'), indent=1)
print('\n-> mapped2.json 已保存')
