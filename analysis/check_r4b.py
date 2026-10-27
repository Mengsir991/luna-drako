import sys,re; sys.path.insert(0,'.')
from hexlib import load_segments
from capstone import *
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS); md.detail=False
LU='TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi'
def flat(p):
    segs=load_segments(p); lo=min(s for s,_ in segs); hi=max(s+len(b)-1 for s,b in segs)
    buf=bytearray(b'\xFF'*(hi-lo+1))
    for s,b in segs: buf[s-lo:s-lo+len(b)]=b
    return lo,bytes(buf)
lo,buf=flat(LU)
def dis(a,b): return list(md.disasm(buf[a-lo:b-lo], a))

for name,site in [('copy1',0x0E08418E),('copy2',0x0E08448E),('copy3',0x0E084792)]:
    ins=dis(site-0x900, site+0x40)
    # 包含 site 的函数：最后一个出现且在 site 之前的 push
    starts=[i.address for i in ins if i.mnemonic.lower().startswith('push') and i.address<site and 'r4' in i.op_str]
    ends  =[i.address for i in ins if i.mnemonic.lower().startswith('pop')  and i.address>site]
    if not starts: print(f'== {name}: 找不到 push'); continue
    fstart=starts[-1]; fend=ends[0] if ends else None
    sub=[i for i in ins if fstart<=i.address<=(fend or site+0x30)]
    print(f'== {name}  P2 点 0x{site:08X}')
    print(f'   函数范围 0x{fstart:08X} .. 0x{fend if fend is not None else site+0x30:08X}  ({len(sub)} 条指令)')
    print(f'   入口: {sub[0].mnemonic} {sub[0].op_str}')
    r4ins=[i for i in sub if re.search(r'(^|\W)r4(\W|$)',i.op_str)]
    print(f'   函数内涉及 r4 的指令 {len(r4ins)} 条:')
    for i in r4ins: print(f'      0x{i.address:08X}  {i.bytes.hex():8s}  {i.mnemonic:8s} {i.op_str}')
    zero=[i for i in sub if i.address<site and re.fullmatch(r'movs\s+r4,\s*#0',i.op_str.strip())]
    after=[i for i in sub if i.address>site and re.search(r'(^|\W)r4(\W|$)',i.op_str)]
    print(f'   -> site 之前是否 movs r4,#0 : {"是 @0x%08X"%zero[0].address if zero else "否"}')
    print(f'   -> site 之后仍用 r4 的指令 : {len(after)} 条 {[hex(i.address) for i in after]}')
    print()
