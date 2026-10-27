"""Read back the 28 patch sites from the device and compare with the patched image."""
import sys, time, re, json; sys.path.insert(0,'.')
import ko1_hid
from ko1_hid import find_nodes, open_node

VID=0x373E; APP=0x0054; BL=0xB054; BASE=0x0E067000; XOR=0x55; CLS_BL=0xB0; OK=(0xA1,0x02)
def pkt(l,c,cmd,args=b''):
    p=bytearray(64); p[2],p[3],p[4],p[5]=0,l,c,cmd; p[6:6+len(args)]=args; return bytes(p)
def pid_of(n):
    m=re.search(r'PID_([0-9A-Fa-f]{4})',str(n.path)); return int(m.group(1),16) if m else 0
def nw(pid): return [n for n in find_nodes(VID,0) if pid_of(n)==pid]

# 0) 设备在吗?
apps=nw(APP); bls=nw(BL)
print(f'当前设备: app 接口 {len(apps)} 个, bootloader 接口 {len(bls)} 个')

# 1) 若在 app 模式, 查版本 + 进 bootloader
if apps:
    for n in sorted(apps, key=lambda x:(0 if 'MI_02' in str(x.path) else 1)):
        try:
            d=open_node(n); d.set_report(pkt(16,0,0x81)); time.sleep(0.15)
            raw=d.get_report(); off=0 if 0xA0<=raw[0]<=0xAF else 1; r=raw[off:]
            print(f'固件版本: {r[6]}.{r[7]}.{r[8]}.{r[9]}' if r[0] in OK else '版本查询无回应')
            d.set_report(pkt(1,0,0,bytes([CLS_BL]))); d.close(); break
        except Exception: continue
    print('已发送进入 bootloader 指令...')
elif not bls:
    sys.exit('鼠标不在线 - 插好再试')

# 2) 等 bootloader 出现
node=None
for _ in range(300):
    c=nw(BL)
    if c: node=c[0]; break
    time.sleep(0.02)
if node is None: sys.exit('bootloader 未出现, 可能超时退回了 - 再跑一次')
bl=open_node(node)

def get():
    raw=bl.get_report(); return raw[(0 if 0xA0<=raw[0]<=0xAF else 1):]
def req(p,tries=300):
    for _ in range(tries):
        bl.set_report(p); time.sleep(0.001); n=get()
        if n[0] in OK and n[4]==CLS_BL: return n
        if n[0]<0xA1:
            for _ in range(40):
                time.sleep(0.002); n=get()
                if n[0] in OK and n[4]==CLS_BL: return n
    raise RuntimeError('no ack')
def read_at(off):
    n=req(pkt(32,CLS_BL,0x83,bytes([32])+(BASE+off).to_bytes(4,'big')))
    return bytes(b^XOR for b in n[11:43])

spec=json.load(open('patch_spec_LUNA_A.json'))
want=open('flash_patched.bin','rb').read()
stock=open('device_full.bin','rb').read()
ok=0
print('\n回读 28 个补丁点:')
for e in spec['edits']:
    off=int(e['address'],16)-BASE
    n=len(bytes.fromhex(e['expected_old_bytes']))
    got=read_at(off&~31)[off%32:off%32+n]
    exp_new=want[off:off+n]
    is_stock = got==stock[off:off+n]
    good = got==exp_new
    ok+=good
    print(f"  {'OK ' if good else 'FAIL'} {e['fn']:>6} 0x{int(e['address'],16):08X}  读回 {got.hex()}  期望 {exp_new.hex()}")
print(f'\n结果: {ok}/28 补丁点在设备上生效 ' + ('✅ 补丁仍在' if ok==28 else '❌ 有异常'))

# 3) 退出 bootloader
try: bl.set_report(pkt(1,CLS_BL,4,bytes([CLS_BL])))
except OSError: pass
bl.close()
print('已发送退出 bootloader, 鼠标即将恢复')
