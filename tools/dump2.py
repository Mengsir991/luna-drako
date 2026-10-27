"""Backup with a correct Intel-HEX writer (extended linear address records)."""
import sys, time, re; sys.path.insert(0,'.')
import ko1_hid
from ko1_hid import find_nodes, open_node

VID=0x373E; APP=0x0054; BL=0xB054
BASE=0x0E067000; XOR=0x55; CLS_BL=0xB0; OK=(0xA1,0x02)
SIZE=int(sys.argv[1],16) if len(sys.argv)>1 else 0x24A00
RAWOUT=sys.argv[2] if len(sys.argv)>2 else 'backup_raw.bin'

def pkt(l,c,cmd,args=b''):
    p=bytearray(64); p[2],p[3],p[4],p[5]=0,l,c,cmd; p[6:6+len(args)]=args; return bytes(p)
def pid_of(n):
    m=re.search(r'PID_([0-9A-Fa-f]{4})',str(n.path)); return int(m.group(1),16) if m else 0
def nodes_with(pid): return [n for n in find_nodes(VID,0) if pid_of(n)==pid]

apps=sorted(nodes_with(APP), key=lambda n:(0 if 'MI_02' in str(n.path) else 1))
d=None
for n in apps:
    try:
        x=open_node(n); x.set_report(pkt(1,0,0,bytes([CLS_BL]))); d=x; break
    except Exception:
        try: x.close()
        except Exception: pass
if d is None: sys.exit('no app interface')
try: d.close()
except Exception: pass
print('  entered bootloader')

node=None
for _ in range(300):
    c=nodes_with(BL)
    if c: node=c[0]; break
    time.sleep(0.02)
if node is None: sys.exit('bootloader not seen')
bl=open_node(node)

def get():
    raw=bl.get_report()
    return raw[(0 if 0xA0<=raw[0]<=0xAF else 1):]

bl.set_report(pkt(6,CLS_BL,0x80)); time.sleep(0.15)
r=get(); print(f'  bootloader status 0x{r[0]:02X}' + (f'  ver {r[8]:x}.{r[9]:02x}.{r[10]:02x}.{r[11]:02x}' if r[0] in OK else ''))

def read_at(off):
    p=pkt(32,CLS_BL,0x83,bytes([32])+(BASE+off).to_bytes(4,'big'))
    for _ in range(200):
        bl.set_report(p); time.sleep(0.001)
        n=get()
        if n[0] in OK and n[4]==CLS_BL:
            return bytes(b^XOR for b in n[11:43])
        if n[0]<0xA1:
            for _ in range(40):
                time.sleep(0.002); n=get()
                if n[0] in OK and n[4]==CLS_BL:
                    return bytes(b^XOR for b in n[11:43])
    raise RuntimeError(f'no ack @{off:#x}')

# 重复读一致性检验 (前 8 个块)
print('  一致性校验:')
stable=True
for t in range(8):
    a=read_at(t*32); b=read_at(t*32)
    if a!=b: stable=False; print(f'    chunk{t}: 两次读取不一致!')
print(f'    前 8 块重复读取: {"一致 OK" if stable else "不稳定 !!!"}')

buf=bytearray(); t0=time.time()
try:
    for off in range(0,SIZE,32):
        buf.extend(read_at(off))
        if len(buf)%(32*256)==0:
            el=time.time()-t0
            print(f'\r  {len(buf)}/{SIZE} ({100*len(buf)/SIZE:5.1f}%) {len(buf)/el/1024:6.1f} KB/s ',end='',flush=True)
finally:
    print(f'\r  {len(buf)} bytes read                                ')
    open(RAWOUT,'wb').write(bytes(buf))
    # 正确的 Intel HEX: 每 64KB 发一条 type-04
    with open(RAWOUT.replace('.bin','.xvi'),'w') as f:
        upper=-1
        for i in range(0,len(buf),16):
            row=bytes(buf[i:i+16]); cur=i>>16
            if cur!=upper:
                rec=bytearray([2,0,0,4,(cur>>8)&0xFF,cur&0xFF])
                rec.append((-sum(rec))&0xFF)
                f.write(':'+rec.hex().upper()+'\n'); upper=cur
            addr=i&0xFFFF
            line=bytearray([len(row),(addr>>8)&0xFF,addr&0xFF,0])+row
            line.append((-sum(line))&0xFF)
            f.write(':'+line.hex().upper()+'\n')
        f.write(':00000001FF\n')
    print(f'  saved {RAWOUT} and {RAWOUT.replace(".bin",".xvi")}')
    try: bl.set_report(pkt(1,CLS_BL,4,bytes([CLS_BL])))
    except OSError: pass
    bl.close()
