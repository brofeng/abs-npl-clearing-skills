# -*- coding: utf-8 -*-
"""两单扫描版发行说明书 OCR（分页并行 + 合并）

★ 为什么不能直接 `04_extract.py --ocr --pages a-b` 多开：
  该模式每次都**整文件重写** `OCR/SM.ocr.txt`，并行跑同一 key 会互相覆盖，
  后完成的那个只带自己那几页（prev 是启动时的旧文件，为空）→ 其余页全丢。
  所以这里由子进程返回「页码 → 文本」字典、由父进程统一按页码合并写盘。
"""
import os, re, sys, time
from concurrent.futures import ProcessPoolExecutor

B = r'E:/兴业银行兴瑞冒烟测试'
TASKS = [
    ('兴瑞2021年第一期', 'SM', '兴瑞2021年第一期不良资产支持证券发行说明书.pdf', 186),
    ('兴瑞2023年第四期', 'SM', '发行说明书_兴瑞2023年第四期_20230911.pdf', 178),
]
CHUNK = 26          # 每个子进程负责的页数
DPI = 200


def ocr_range(args):
    proj, key, fn, lo, hi = args
    import fitz
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    doc = fitz.open(os.path.join(B, proj, '01_下载文档', fn))
    out = {}
    t0 = time.time()
    for i in range(lo - 1, min(hi, doc.page_count)):
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(DPI / 72, DPI / 72))
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        res, _ = ocr(img)
        out[i + 1] = "\n".join(x[1] for x in (res or []))
    return proj, lo, hi, out, round(time.time() - t0, 1)


if __name__ == "__main__":
    jobs = []
    for proj, key, fn, npg in TASKS:
        for lo in range(1, npg + 1, CHUNK):
            jobs.append((proj, key, fn, lo, min(lo + CHUNK - 1, npg)))

    print(f'分片 {len(jobs)} 个，{CHUNK} 页/片，{DPI}dpi', flush=True)
    merged = {}
    with ProcessPoolExecutor(max_workers=6) as ex:
        for proj, lo, hi, pages, sec in ex.map(ocr_range, jobs):
            merged.setdefault(proj, {}).update(pages)
            print(f'  {proj} p{lo}-{hi}  {len(pages)} 页  {sec}s', flush=True)

    for proj, key, fn, npg in TASKS:
        d = merged.get(proj) or {}
        od = os.path.join(B, proj, '02_提取数据', 'OCR')
        os.makedirs(od, exist_ok=True)
        body = "\n\n".join(f"<<<PAGE {i}>>>\n{d.get(i, '')}" for i in sorted(d))
        p = os.path.join(od, f'{key}.ocr.txt')
        with open(p, 'w', encoding='utf-8', newline='') as f:
            f.write(body)
        print(f'写盘 {proj} {key}  {len(d)} 页  {os.path.getsize(p):,}B', flush=True)
    print('SM OCR DONE', flush=True)
