import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from hexlib import load_segments

import re, json
from capstone import *

# inputs - adjust if your layout differs
STOCK = os.environ.get('STOCK', os.path.join('..', 'tools', 'TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi'))       # Luna official image
KO_HEX = os.environ.get('KO_HEX', os.environ.get('KO1_HEX', '54H_mouse_Cpurad_App_v01.09.02.05.hex'))  # hyperdrako stock hex
HYPERDRAKO_SPEC = os.environ.get('HYPERDRAKO_SPEC', 'patch_spec_A.json')  # hyperdrako out/patch_spec_A.json

from capstone import *
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS); md.detail=False
KO=KO_HEX
LU=STOCK
MOVImm=re.compile(r'^\s*r(\d+),\s*#(0x[0-9a-f]+|\d+)$')
MOVReg=re.compile(r'^\s*r(\d+),\s*r(\d+)$')
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
        ma=MOVImm.match(a.op_str)
        mb=MOVImm.match(b.op_str); mr=MOVReg.match(b.op_str)
        if not ma: continue
        val=int(ma.group(2),0); vreg=int(ma.group(1))
        if mb:
            reg=int(mb.group(2),0); form='P1'
        elif mr and mr.group(1)=='0' and mr.group(2)==str(vreg):
            reg=val; form='P3'
        else:
            reg=None; form='P2'
        out.append(dict(addr=c.address, ins_addr=a.address, bl=c.address, reg=reg, val=val,
                        form=form, a=f'{a.mnemonic} {a.op_str}', b=f'{b.mnemonic} {b.op_str}',
                        bytes_a=a.bytes.hex(), bytes_b=b.bytes.hex(), off_a=a.address-0x0E067000, off_b=b.address-0x0E067000))
    return out

k=writes(KO,'#0xe06bdb8'); l=writes(LU,'#0xe06b19c')
print(f'KO-ONE 写入点 {len(k)};  LUNA 写入点 {len(l)}')
kk=[w for w in k if w['reg'] is not None]; ll=[w for w in l if w['reg'] is not None]
print(f'可解析出寄存器号: KO {len(kk)}, LU {len(ll)}')
sig=lambda ws:[(w['reg'],w['val']) for w in ws]
print(f'\nKO 序列 == LU 序列 ? {sig(kk)==sig(ll)}')
import difflib
sm=difflib.SequenceMatcher(None, sig(kk), sig(ll))
print(f'相似度: {sm.ratio():.4f}   匹配块数: {len(sm.get_matching_blocks())}')
print(f'\nKO 前 {min(12,len(kk))} 条:'); 
for w in kk[:12]: print(f"   0x{w['addr']:08X} form={w['form']}  reg={w['reg']:#04x} val={w['val']:#04x}   [{w['a']} | {w['b']}]")
json.dump(dict(ko=k,lu=l), open('writes.json','w'), indent=0)
print('\n-> writes.json 已保存')
