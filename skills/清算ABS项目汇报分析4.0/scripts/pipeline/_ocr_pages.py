# -*- coding: utf-8 -*-
"""对指定扫描件重跑若干页 OCR（更高 dpi），并**就地替换**已有 .ocr.txt 的对应页

用途：个别扫描件整体 OCR 可用，但关键表（日期概况 / 本息兑付）那几页识别错，
      整份重跑不值当（40 页 × 100 秒），只补那几页即可。
"""
import os, re, sys
import fitz
import numpy as np

B = r'E:/兴业银行兴瑞冒烟测试'
# (项目, 键, 文件名, 页码列表, dpi)
JOBS = [
    ('兴瑞2021年第二期', 'TR04', '受托机构报告_兴瑞2021年第二期_20220429.pdf', [32, 33, 34], 300),
    ('兴瑞2021年第二期', 'TR09', '受托机构报告_兴瑞2021年第二期_20230427.pdf', [32, 33, 34], 300),
]


def run(proj, key, fn, pages, dpi):
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    doc = fitz.open(os.path.join(B, proj, '01_下载文档', fn))
    new = {}
    for pn in pages:
        if pn > doc.page_count:
            continue
        pix = doc[pn - 1].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        res, _ = ocr(img)
        new[pn] = "\n".join(x[1] for x in (res or []))
    op = os.path.join(B, proj, '02_提取数据', 'OCR', f'{key}.ocr.txt')
    old = open(op, encoding='utf-8').read()
    blocks = dict((int(a), b) for a, b in
                  re.findall(r"<<<PAGE (\d+)>>>(.*?)(?=<<<PAGE|\Z)", old, re.S))
    blocks.update(new)
    body = "\n\n".join(f"<<<PAGE {i}>>>\n{blocks[i]}" for i in sorted(blocks))
    with open(op, 'w', encoding='utf-8', newline='') as f:
        f.write(body)
    print(f'{proj} {key} 重跑 {sorted(new)} 页 → {os.path.getsize(op):,}B', flush=True)


if __name__ == '__main__':
    for j in JOBS:
        run(*j)
    print('PAGE REFRESH DONE')
