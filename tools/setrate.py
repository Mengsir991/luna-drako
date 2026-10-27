"""Set polling rate on the TYPE33 EVO via the 8K receiver (app config protocol)."""
import sys, time, re; sys.path.insert(0,'.')
import ko1_hid
from ko1_hid import find_nodes, open_node
VID=0x373E; PID=int(sys.argv[2],16) if len(sys.argv)>2 else 0x0084
VAL={'1':1,'1000':1,'32':32,'2000':32,'64':64,'4000':64,'128':128,'8000':128}[sys.argv[1]]
PROFILE=1
def pid_of(n):
    m=re.search(r'PID_([0-9A-Fa-f]{4})',str(n.path)); return int(m.group(1),16) if m else 0
def cfg(dev, cmd, a6=0, a7=0, has7=False):
    p=bytearray(64); p[2],p[3],p[4],p[5]=2,2,1,cmd
    p[6]=a6
    if has7: p[7]=a7
    dev.set_report(bytes(p)); time.sleep(0.01)
    raw=dev.get_report(); off=0 if 0xA0<=raw[0]<=0xAF else 1
    return raw[off:]
cands=[n for n in find_nodes(VID,0) if pid_of(n)==PID]
cands.sort(key=lambda n:(0 if 'MI_02' in str(n.path) else 1))
dev=open_node(cands[0])
try:
    cfg(dev,0x00,PROFILE,VAL,has7=True); time.sleep(0.3)
    rp=cfg(dev,0x80,PROFILE); pr=rp[7]
    hm=cfg(dev,0x8B,PROFILE)[7]
    print(f'回报率寄存值 = {pr} -> ' + {1:'1000 Hz',32:'2000 Hz',64:'4000 Hz',128:'8000 Hz'}.get(pr,'?'))
    print(f'HyperMode    = {hm}')
    print('✅ 8000 Hz 已生效' if pr==128 else '⚠️ 未变成 8000')
finally:
    dev.close()
