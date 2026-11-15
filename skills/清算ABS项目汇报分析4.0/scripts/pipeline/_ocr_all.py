# -*- coding: utf-8 -*-
"""兴瑞全量 OCR（并行）

策略（按实测定的）：
· ZZ 中债资信评级：只需 p1–p10 —— 摘要段含「发行规模分层 + 预计回收 + 回收率」，
  后面是交易结构/基础资产分析，取数用不到；36 页全跑是白烧 3 倍时间。
· LQAUDIT/LQREVIEW 清算件：全页 —— 兑付表与现金流表位置逐单不同，不能猜。
· TR 受托报告：全页（少数扫描件）。
并行：5 进程（RapidOCR 自身多线程，进程数过大会互相抢核反而慢）。
"""
import os, sys, json, subprocess
from concurrent.futures import ThreadPoolExecutor

PY = sys.executable
B = r'E:/兴业银行兴瑞冒烟测试'
S = os.path.join(B, '脚本')
ZZ_PAGES = "1-10"


def job(args):
    n, keys, pages = args
    pj = os.path.join(B, n)
    cmd = [PY, '04_extract.py', '--proj', pj, '--ocr', '--ocr-keys', ','.join(keys)]
    if pages:
        cmd += ['--pages', pages]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', cwd=S)
    return n, keys, r.returncode, (r.stdout or '')[-400:], (r.stderr or '')[-400:]


tasks = []
for n in sorted(d for d in os.listdir(B) if d.startswith('兴瑞')):
    pj = os.path.join(B, n)
    idx = json.load(open(os.path.join(pj, '02_提取数据', '_text_index.json'), encoding='utf-8'))
    need = [r['key'] for r in idx if r.get('mode') in ('ocr-needed', 'ocr-partial')]
    if 'ZZ' in need:
        tasks.append((n, ['ZZ'], ZZ_PAGES))
    rest = [k for k in need if k != 'ZZ' and (k.startswith('LQ') or
            (k.startswith('TR') and k != 'TRREVIEW'))]
    if rest:
        tasks.append((n, rest, None))

print(f'任务 {len(tasks)} 个', flush=True)
with ThreadPoolExecutor(max_workers=5) as ex:
    for n, keys, rc, out, err in ex.map(job, tasks):
        print(f'[{ "OK " if rc==0 else "ERR"}] {n:18s} {keys}', flush=True)
        if rc:
            print('   ', (err or out)[-250:], flush=True)
print('ALL DONE')
