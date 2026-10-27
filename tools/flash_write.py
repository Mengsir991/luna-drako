"""erase -> program -> verify for the Lunafury TYPE33 EVO."""
import sys, time, re, argparse, struct; sys.path.insert(0,'.')
import ko1_hid
from ko1_hid import find_nodes, open_node

VID=0x373E; APP=0x0054; BL=0xB054
BASE=0x0E067000; XOR=0x55; CLS_BL=0xB0; OK=(0xA1,0x02)
def pkt(l,c,cmd,args=b''):
    p=bytearray(64); p[2],p[3],p[4],p[5]=0,l,c,cmd; p[6:6+len(args)]=args; return bytes(p)
def pid_of(n):
    m=re.search(r'PID_([0-9A-Fa-f]{4})',str(n.path)); return int(m.group(1),16) if m else 0
def nodes_with(pid): return [n for n in find_nodes(VID,0) if pid_of(n)==pid]

def build_program_packets(base,img):
    out=[]
    for off in range(0,len(img),32):
        ch=img[off:off+32]; n=len(ch)
        p=bytearray(64)
        p[2],p[3],p[4],p[5],p[6]=0,n+5,CLS_BL,2,n
        p[7:11]=(base+off).to_bytes(4,'big'); p[11:11+n]=ch
        for i in range(11,64): p[i]^=XOR
        out.append((base+off,n,bytes(p)))
    return out

def sanity(img):
    sp,reset=struct.unpack_from('<II',img,0)
    ok=True
    if not (0x20000000<=sp<0x30000000): print(f'  !! SP {sp:#x} 不像 RAM'); ok=False
    if not (reset&1 and BASE<=reset<BASE+len(img)): print(f'  !! reset {reset:#x} 异常'); ok=False
    print(f'  SP={sp:#010x}  Reset={reset:#010x}  长度={len(img)}  {"OK" if ok else "!! 拒绝"}')
    return ok

def enter_bl():
    for n in sorted(nodes_with(APP), key=lambda x:(0 if 'MI_02' in str(x.path) else 1)):
        try:
            d=open_node(n); d.set_report(pkt(1,0,0,bytes([CLS_BL]))); d.close(); return True
        except Exception: continue
    return False

def open_bl():
    for _ in range(300):
        c=nodes_with(BL)
        if c:
            return open_node(c[0])
        time.sleep(0.02)
    raise SystemExit('bootloader 未出现')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('image')
    ap.add_argument('--apply',action='store_true',help='真的写入; 不加则 dry-run')
    ap.add_argument('--skip-erase',action='store_true')
    a=ap.parse_args()
    img=open(a.image,'rb').read()
    print(f'镜像: {a.image}  {len(img)} bytes @ {BASE:#x}')
    import hashlib; print(f'  sha256 {hashlib.sha256(img).hexdigest()}')
    if not sanity(img): raise SystemExit('sanity 未通过')
    pkts=build_program_packets(BASE,img)
    print(f'  编程包: {len(pkts)} 个')
    print(f'  首包: {pkts[0][2].hex(" ")}')
    if not a.apply:
        print('\nDRY RUN: 未写入, 未擦除。确认无误后加 --apply')
        return
    print('\n进入 bootloader...'); enter_bl(); time.sleep(1.0)
    bl=open_bl()
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
    try:
        if not a.skip_erase:
            print('擦除中...'); t0=time.time()
            bl.set_report(pkt(8,CLS_BL,1))
            done=False
            while time.time()-t0<30:
                time.sleep(0.02); n=get()
                if n[0] in OK: done=True; break
            print(f'  erase {"完成" if done else "超时!!"}')
            if not done: raise SystemExit('erase failed')
        print('写入中...'); t0=time.time()
        for i,(_,_,p) in enumerate(pkts,1):
            req(p)
            if i%256==0 or i==len(pkts):
                el=time.time()-t0; eta=el*(len(pkts)-i)/i if i else 0
                sys.stdout.write(f'\r  {i}/{len(pkts)} ({100*i/len(pkts):5.1f}%) eta {eta:4.0f}s '); sys.stdout.flush()
        print()
        print('校验中...'); bad=0
        for off in range(0,len(img),32):
            if read_at(off)[:min(32,len(img)-off)] != img[off:off+32][:min(32,len(img)-off)]:
                bad+=1; print(f'\n  校验不符 @ {BASE+off:#x}')
                if bad>3: break
        print(f'  校验{"通过" if bad==0 else "失败!!"}')
        try: bl.set_report(pkt(1,CLS_BL,4,bytes([CLS_BL])))
        except OSError: pass
    finally:
        bl.close()
    print('完成。若鼠标未自动恢复, 拔插一次。')

if __name__=='__main__':
    main()
