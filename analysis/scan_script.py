import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from hexlib import load_segments

import re
from capstone import *

# inputs - adjust if your layout differs
STOCK = os.environ.get('STOCK', os.path.join('..', 'tools', 'TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi'))       # Luna official image
KO_HEX = os.environ.get('KO_HEX', os.environ.get('KO1_HEX', '54H_mouse_Cpurad_App_v01.09.02.05.hex'))  # hyperdrako stock hex
HYPERDRAKO_SPEC = os.environ.get('HYPERDRAKO_SPEC', 'patch_spec_A.json')  # hyperdrako out/patch_spec_A.json

from capstone import *
from collections import defaultdict
LU=STOCK
KO=KO_HEX
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS); md.detail=False
MOVImm=re.compile(r'^\s*r(\d+),\s*#(0x[0-9a-f]+|\d+)$')
def disasm_segments(path):
    out=[]
    for s,b in load_segments(path):
        a=s if s%2==0 else s  # thumb 对齐
        off=0 if s%2==0 else 1
        out.extend(list(md.disasm(b[off:], s+off)))
    out.sort(key=lambda i:i.address)
    return out

def find_scripts(name,path):
    ins=disasm_segments(path)
    n=len(ins); idx={i.address:i for i in ins}
    print(f'== {name}: 逐段反汇编得 {len(ins)} 条指令')
    groups=defaultdict(list)
    for i in range(n-2):
        a,b,c=ins[i],ins[i+1],ins[i+2]
        if c.mnemonic!='bl': continue
        if a.mnemonic not in ('movs','mov') or b.mnemonic not in ('movs','mov'): continue
        ma,mb=MOVImm.match(a.op_str),MOVImm.match(b.op_str)
        if not(ma and mb): continue
        val=int(ma.group(2),0); reg=int(mb.group(2),0)
        if val>0xFF or reg>0xFF: continue
        groups[c.op_str].append((c.address,reg,val,i))
    res=[]
    for target,items in groups.items():
        if len(items)<8: continue
        items.sort()
        clusters=[]; cur=[items[0]]
        for prev,it in zip(items,items[1:]):
            if it[3]-prev[3]<=6: cur.append(it)
            else: clusters.append(cur); cur=[it]
        clusters.append(cur)
        for cl in clusters:
            if len(cl)>=8: res.append((target,cl))
    res.sort(key=lambda x:-len(x[1]))
    print(f'   script region 命中: {len(res)} 个\n')
    for target,cl in res[:5]:
        print(f'   [{len(cl):>3} 次] bl {target}  首址 0x{cl[0][0]:08X}')
        print(f'        寄存器: '+', '.join(f'{r:#04x}' for r,_,_,_ in cl[:20]))
    return ins,res

for name,path in [('KO-ONE',KO),('LUNA-EVO',LU)]:
    find_scripts(name,path); print()
