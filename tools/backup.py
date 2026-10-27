"""One-shot backup: enter bootloader -> dump -> let it reboot back to app."""
import sys, time, re; sys.path.insert(0,'.')
import ko1_hid
from ko1_hid import find_nodes, open_node

VID=0x373E; APP=0x0054; BL=0xB054
BASE=0x0E067000; XOR=0x55; CLS_BL=0xB0; OK=(0xA1,0x02)
SIZE=int(sys.argv[1],16) if len(sys.argv)>1 else 0x24A00
OUT=sys.argv[2] if len(sys.argv)>2 else 'backup_original.xvi'

def pkt(l,c,cmd,args=b''):
    p=bytearray(64); p[2],p[3],p[4],p[5]=0,l,c,cmd; p[6:6+len(args)]=args; return bytes(p)
def pid_of(n):
    m=re.search(r'PID_([0-9A-Fa-f]{4})',str(n.path)); return int(m.group(1),16) if m else 0
def nodes_with(pid):
    return [n for n in find_nodes(VID,0) if pid_of(n)==pid]

# 1) enter bootloader via the app config interface (MI_02 answered earlier)
apps=sorted(nodes_with(APP), key=lambda n:(0 if 'MI_02' in str(n.path) else 1))
dev=None
for n in apps:
    try:
        d=open_node(n)
        d.set_report(pkt(1,0,0,bytes([CLS_BL]))); dev=d; break
    except Exception:
        try: d.close()
        except Exception: pass
if dev is None:
    sys.exit('could not open any app interface')
print('  sent enter-bootloader')
try: dev.close()
except Exception: pass

# 2) wait for the bootloader node to appear
node=None
for _ in range(200):
    cands=nodes_with(BL)
    if cands: node=cands[0]; break
    time.sleep(0.02)
if node is None:
    sys.exit('bootloader never appeared (it may exit too fast to catch)')
print(f'  bootloader online: {pid_of(node):04X}')

bl=open_node(node)
def get():
    raw=bl.get_report()
    return raw[(0 if 0xA0<=raw[0]<=0xAF else 1):]
bl.set_report(pkt(6,CLS_BL,0x80)); time.sleep(0.15)
r=get()
print(f'  bootloader status=0x{r[0]:02X}' + (f'  ver {r[8]:x}.{r[9]:02x}.{r[10]:02x}.{r[11]:02x}' if r[0] in OK else ''))
def req(p,tries=300):
    for _ in range(tries):
        bl.set_report(p); time.sleep(0.001)
        n=get()
        if n[0] in OK and n[4]==CLS_BL: return n
        if n[0]<0xA1:
            for _ in range(30):
                time.sleep(0.002); n=get()
                if n[0] in OK and n[4]==CLS_BL: return n
    raise RuntimeError(f'no ack at offset')
buf=bytearray(); t0=time.time()
try:
    for off in range(0,SIZE,32):
        n=req(pkt(32,CLS_BL,0x83,bytes([32])+(BASE+off).to_bytes(4,'big')))
        buf.extend(bytes(b^XOR for b in n[11:43]))
        if len(buf)%(32*128)==0:
            el=time.time()-t0
            print(f'\r  {len(buf)}/{SIZE}  ({100*len(buf)/SIZE:5.1f}%)  {len(buf)/el/1024:6.1f} KB/s  ',end='',flush=True)
finally:
    print(f'\r  {len(buf)}/{SIZE} bytes read                                 ')
    with open(OUT,'w') as f:
        for i in range(0,len(buf),16):
            row=buf[i:i+16]
            line=bytearray([len(row),(i>>8)&0xFF,i&0xFF,0x00])+row
            line.append((-sum(line))&0xFF)
            f.write(':'+line.hex().upper()+'\n')
        f.write(':00000001FF\n')
    print(f'  saved {OUT}')
    try:
        bl.set_report(pkt(1,CLS_BL,4,bytes([CLS_BL])))
    except OSError: pass
    bl.close()
