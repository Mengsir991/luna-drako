"""Enable/disable HyperMode (竞技模式) on the Lunafury TYPE33 EVO - app config protocol."""
import sys, time, re; sys.path.insert(0,'.')
import ko1_hid
from ko1_hid import find_nodes, open_node

VID=0x373E; APP=int(sys.argv[2],16) if len(sys.argv)>2 else 0x0084   # 0084=8K接收器, 0054=有线
PROFILE=1
def pid_of(n):
    m=re.search(r'PID_([0-9A-Fa-f]{4})',str(n.path)); return int(m.group(1),16) if m else 0

def open_app():
    cands=[n for n in find_nodes(VID,0) if pid_of(n)==APP]
    cands.sort(key=lambda n:(0 if 'MI_02' in str(n.path) else 1))
    for n in cands:
        try: return open_node(n)
        except Exception: continue
    raise SystemExit('打不开任何 app 接口 - 关掉 Luna 网页驱动再试')

def cfg(dev, cmd, a6=0, a7=0, has7=False):
    p=bytearray(64); p[2],p[3],p[4],p[5]=2,2,1,cmd
    p[6]=a6
    if has7: p[7]=a7
    dev.set_report(bytes(p)); time.sleep(0.01)
    raw=dev.get_report()
    off=0 if 0xA0<=raw[0]<=0xAF else 1   # 回应可能带 1 字节偏移
    return raw[off:]

dev=open_app()
try:
    # 当前状态
    r=cfg(dev,0x8B,PROFILE);              hm=r[7] if len(r)>7 else None
    rp=cfg(dev,0x80,PROFILE);             pr=rp[7] if len(rp)>7 else None
    print(f'当前 HyperMode = {hm}   回报率寄存值 = {pr} (原始回应: {bytes(rp[:10]).hex(" ")})')

    if len(sys.argv)>1 and sys.argv[1] in ('on','off'):
        val=1 if sys.argv[1]=='on' else 0
        cfg(dev,0x0B,PROFILE,val,has7=True); time.sleep(0.15)
        r2=cfg(dev,0x8B,PROFILE);        hm2=r2[7] if len(r2)>7 else None
        rp2=cfg(dev,0x80,PROFILE);       pr2=rp2[7] if len(rp2)>7 else None
        print(f'设置后 HyperMode = {hm2}   回报率寄存值 = {pr2}')
        print('✅ 已生效' if hm2==val else '❌ 未生效')
    else:
        print('(只读查询。要切换: python hyper.py on / off)')
finally:
    dev.close()
