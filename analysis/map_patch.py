import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from hexlib import load_segments

import json

# inputs - adjust if your layout differs
STOCK = os.environ.get('STOCK', os.path.join('..', 'tools', 'TYPE33_Mouse_54H20_App_v0.0.1.48_20261013.xvi'))       # Luna official image
KO_HEX = os.environ.get('KO_HEX', os.environ.get('KO1_HEX', '54H_mouse_Cpurad_App_v01.09.02.05.hex'))  # hyperdrako stock hex
HYPERDRAKO_SPEC = os.environ.get('HYPERDRAKO_SPEC', 'patch_spec_A.json')  # hyperdrako out/patch_spec_A.json

d=json.load(open('writes.json'))
ko=d['ko']; lu=d['lu']
spec=json.load(open(r'HYPERDRAKO_SPEC'))
BASE=0x0E067000
ko_by_ins={w['ins_addr']:w for w in ko}
# patch_spec 的 address 指向 movs/mov 那条指令本身
edit_sites={}
for e in spec['edits']:
    a=int(e['address'],16); edit_sites.setdefault(a,[]).append(e)
print(f'KO-ONE patch_spec_A: {len(spec["edits"])} 处编辑, 覆盖 {len(edit_sites)} 条指令\n')

def sig(ws): return tuple((w['reg'],w['val']) for w in ws)
lu_sig=sig(lu)

results=[]
for addr, ed in sorted(edit_sites.items()):
    w=ko_by_ins.get(addr)
    if w is None:
        # P3b 的 address 指向第二条 mov r0,r1
        for cand in ko:
            if cand['bl']==addr or abs(cand['ins_addr']-addr)<=4:
                w=cand; break
    if w is None:
        print(f'  ⚠ KO 0x{addr:08X} 未映射'); continue
    i=ko.index(w)
    C=5
    window=ko[max(0,i-C):i+C+1]
    ws=sig(window)
    # 在 LU 序列中找该窗口
    hit=None
    for j in range(len(lu)-len(ws)+1):
        if sig(lu[j:j+len(ws)])==ws: hit=j; break
    if hit is None:
        results.append((addr,w,None,None,ed)); continue
    center=lu[hit+C]
    results.append((addr,w,center,window and None,ed))

ok=sum(1 for r in results if r[2])
print(f'成功映射 {ok}/{len(results)} 个 KO 补丁点到 LUNA\n')
print(f"{'KO 指令':>12}  {'reg':>5} {'val':>5} {'OLD->NEW':>14}   {'LUNA 指令':>12}  形态")
print('-'*88)
for addr,w,lu_w,_,ed in results:
    newv = ed[0].get('new_bytes')
    if lu_w:
        print(f"0x{addr:08X}  {w['reg']:#5x} {w['val']:#5x} {w['val']:>#5x}->{int(ed[0]['new_bytes'],16):>#5x}   0x{lu_w['ins_addr']:08X}  {'相同' if lu_w['reg']==w['reg'] and lu_w['val']==w['val'] else '不一致'}")
    else:
        print(f"0x{addr:08X}  {w['reg']:#5x} {w['val']:#5x}   -> {'未定位'}")
json.dump([{'ko_addr':a,'reg':w['reg'],'val':w['val'],'new':int(e[0]['new_bytes'],16),
            'lu_addr':(x['ins_addr'] if x else None),'lu_form':(x['form'] if x else None),
            'lu_a':(x['a'] if x else None),'lu_b':(x['b'] if x else None),
            'lu_bytes_a':(x['bytes_a'] if x else None),'lu_bytes_b':(x['bytes_b'] if x else None),
            'lu_off_a':(x['off_a'] if x else None),'lu_off_b':(x['off_b'] if x else None)}
           for a,w,x,_,e in results], open('mapped.json','w'), indent=1)
print('\n-> mapped.json 已保存')
