# -*- coding: utf-8 -*-
"""补齐 3 单缺的 LQAUDIT / TR OCR（并行 4 进程）"""
import os, sys, subprocess
from concurrent.futures import ThreadPoolExecutor

PY = sys.executable
B = r'E:/兴业银行兴瑞冒烟测试'
S = os.path.join(B, '脚本')

TASKS = [
    ('兴瑞2021年第一期', ['LQAUDIT']),
    ('兴瑞2021年第二期', ['TR04']),
    ('兴瑞2021年第二期', ['TR09']),
    ('兴瑞2021年第二期', ['LQAUDIT']),
    ('兴瑞2022年第一期', ['TR05']),
    ('兴瑞2022年第一期', ['LQAUDIT']),
]


def job(t):
    n, keys = t
    cmd = [PY, '04_extract.py', '--proj', os.path.join(B, n),
           '--ocr', '--ocr-keys', ','.join(keys)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', cwd=S)
    return n, keys, r.returncode, (r.stdout or '')[-300:], (r.stderr or '')[-300:]


with ThreadPoolExecutor(max_workers=4) as ex:
    for n, keys, rc, out, err in ex.map(job, TASKS):
        print(f'[{"OK " if rc == 0 else "ERR"}] {n:18s} {keys}', flush=True)
        if rc:
            print('   ', (err or out)[-250:], flush=True)
print('REST OCR DONE')
