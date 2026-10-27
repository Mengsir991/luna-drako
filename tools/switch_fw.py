"""一键切换 Luna 固件版本。用法: python switch_fw.py <hybrid|fps|stock>"""
import sys, subprocess, os

FW = {
    'hybrid': ('flash_hybrid.bin', '混合版: HyperMode 开=锁 20k / 平时=出厂自适应(省电)'),
    'fps':    ('flash_fps.bin',    '全 20k 满血版: 任何模式都锁 20000 fps'),
    'stock':  ('device_cur.bin',   '出厂帧率版: 仅保留降 DPI 补丁, 帧率完全原厂'),
}

def main():
    if len(sys.argv) < 2 or sys.argv[1].lower() not in FW:
        print('用法: python switch_fw.py <版本>')
        print('  hybrid  - 混合版 (HyperMode 开=20k 锁定, 平时省电) [推荐日常]')
        print('  fps     - 全 20k 满血版 [竞技/不计功耗]')
        print('  stock   - 出厂帧率版 [只保留降 DPI 补丁]')
        sys.exit(1)
    name=sys.argv[1].lower()
    img,desc=FW[name]
    if not os.path.exists(img): sys.exit(f'镜像不存在: {img}')
    here=os.path.dirname(os.path.abspath(__file__))
    print(f'切换到: {name} - {desc}')
    print('注意: 鼠标必须插着 USB 线!\n')
    r=subprocess.run([sys.executable, os.path.join(here,'flash_write.py'), '--apply', img])
    if r.returncode==0:
        print(f'\n✅ 刷写完成, 拔掉 USB 线即可生效 ({name})')

if __name__=='__main__':
    main()
