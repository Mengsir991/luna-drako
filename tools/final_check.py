import sys, re, json; sys.path.insert(0,'.')
from hexlib import load_segments
from capstone import *
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS); md.detail=False

def loadimap(path):
    ins=[]
    for s,b in load_segments(path):
        off=0 if s%2==0 else 1
        ins.extend(list(md.disasm(b[off:], s+off)))
    ins.sort(key=lambda i:i.address)
    return {i.address:i for i in ins}, len(ins)

NUM=re.compile(r'#(0x[0-9a-fA-F]+|\d+)')
def imm_of(text):
    m=NUM.search(text)
    return int(m.group(1),0) if m else None

A,na=loadimap('TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi')
B,nb=loadimap('patched_TYPE33_A.xvi')
spec=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','patch_spec_LUNA_A.json')))
ok=True
print('位点            编码  补丁前                   补丁后                   判定')
print('-'*84)
for e in spec['edits']:
    addr=int(e['address'],16); enc=e['encoding']
    o=A.get(addr); n=B.get(addr)
    ot=f'{o.mnemonic} {o.op_str}' if o else '?'
    nt=f'{n.mnemonic} {n.op_str}' if n else '?'
    # P2 的 new_bytes 是两字节机器码 0221(=movs r1,#2), 其余是单字节立即数
    want = 0x02 if enc=='P2' else int(e['new_bytes'],16)
    if enc in ('P1','P3a','P2'):
        good = bool(n) and n.mnemonic=='movs' and n.op_str.startswith('r1,') and imm_of(nt)==want
    elif enc=='P3b':
        good = bool(n) and n.mnemonic=='movs' and n.op_str.startswith('r0,') and imm_of(nt)==0x4f
    else:
        good=False
    ok &= good
    print(f"{e['fn']:>5} 0x{addr:08X} {enc:>4}  {ot:26s} {nt:26s} {'OK' if good else 'FAIL'}")
print('-'*84)
print(f"结果: {'全部 %d 处通过 PASS'%len(spec['edits']) if ok else '存在失败项'}")
print(f"结构完整性: {na} -> {nb} 条指令 ({'OK' if na==nb else '异常'})")
