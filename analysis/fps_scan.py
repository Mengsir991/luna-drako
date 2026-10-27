"""Locate frame-rate register writes (0x42/0x53/0x62/0x6D/0x6E) in every sensor script region."""
import sys, re; sys.path.insert(0,'.')
from hexlib import load_segments
from capstone import *
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS); md.detail=False
IMM=re.compile(r'^\s*r(\d+),\s*#(0x[0-9a-f]+|\d+)$')
REG=re.compile(r'^\s*r(\d+),\s*r(\d+)$')
HELPER='#0xe06b19c'
LU='TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi'
TARGET_REGS={0x42,0x53,0x62,0x6D,0x6E,0x6d,0x6e}

ins=[]
for s,b in load_segments(LU):
    off=0 if s%2==0 else 1
    ins.extend(list(md.disasm(b[off:], s+off)))
ins.sort(key=lambda i:i.address)

# 所有写寄存器调用 (a=val, b=reg, c=bl helper) - 形态与之前一致
writes=[]
for i in range(len(ins)-2):
    a,b,c=ins[i],ins[i+1],ins[i+2]
    if c.mnemonic!='bl' or c.op_str!=HELPER: continue
    ma=IMM.match(a.op_str); mb=IMM.match(b.op_str); mr=REG.match(b.op_str)
    if not ma: continue
    val=int(ma.group(2),0)
    reg=int(mb.group(2),0) if mb else (val if (mr and mr.group(1)=='0' and mr.group(2)==ma.group(1)) else None)
    writes.append(dict(ins_a=a.address, ins_b=b.address, bl=c.address, reg=reg, val=val,
                       a_raw=f'{a.mnemonic} {a.op_str}', b_raw=f'{b.mnemonic} {b.op_str}',
                       bytes_a=a.bytes.hex(), bytes_b=b.bytes.hex()))

# 按 KO-ONE 的 7 个脚本簇位置聚簇 (bl 地址间隔 <= 0x40 归簇)
clusters=[]; cur=[]
for w in sorted(writes, key=lambda w:w['bl']):
    if cur and w['bl']-cur[-1]['bl']>0x40:
        clusters.append(cur); cur=[]
    cur.append(w)
if cur: clusters.append(cur)
clusters=[c for c in clusters if len(c)>=8]

FRAME={0x42:'UNIT',0x53:'FPS_MAX',0x62:'FPS_MIN',0x6D:'UNK1',0x6E:'UNK2'}
print(f'Luna: {len(writes)} 写入点, {len(clusters)} 个脚本区\n')
for idx,cl in enumerate(clusters):
    hits=[w for w in cl if w['reg'] in TARGET_REGS]
    print(f'脚本 #{idx+1}: {len(cl)} 写入点, 区间 0x{cl[0]["bl"]:08X}..0x{cl[-1]["bl"]:08X}')
    if not hits:
        print('   (无帧率寄存器写入)\n'); continue
    for w in sorted(hits,key=lambda w:w['bl']):
        name=FRAME.get(w['reg'],hex(w['reg']))
        print(f"   0x{w['ins_a']:08X}  {name:8s} reg {w['reg']:#04x} = {w['val']:#04x}   [{w['a_raw']} | {w['b_raw']}]  bytes {w['bytes_a']}/{w['bytes_b']}")
    print()
