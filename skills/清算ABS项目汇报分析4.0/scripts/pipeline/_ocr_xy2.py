# -*- coding: utf-8 -*-
"""坐标 OCR 缓存：把指定页的每个文本框存成 (x_center, y_center, text)

★ 为什么要缓存坐标而不只用纯文本：
  兴瑞 2021/2023 这两批说明书是**扫描件**，表格在 PDF 里是"转置 + 并排"排版的：
    · 转置：类别标签（(0,5]/60万元以上）在表格**最后一行**，指标名（贷款余额/
      余额占比/贷款笔数…）在**左侧第一列**；
    · 并排：同一页上常有 2–3 张表横向并列（p110 就是三张），它们的行 y 完全相同。
  纯文本 OCR 把两批打散后按顺序配对，每个维度都会错位，**而错位后合计照样能对上**
  （合计是最后一个值，永远单独在那儿），属于最难发现的一类错。
  只有拿到 x 坐标才能把并排的表切开、把值落到正确的类别列。

产物：02_提取数据/OCR/_xy.json
  {"<页>": [[x, y, text], ...], ...}
"""
import json
import os
import sys

import fitz
import numpy as np

B = r'E:/兴业银行兴瑞冒烟测试'
DPI = 250


def ocr_page(ocr, doc, pn):
    pix = doc[pn - 1].get_pixmap(matrix=fitz.Matrix(DPI / 72, DPI / 72))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    res, _ = ocr(img)
    out = []
    for box, txt, _s in (res or []):
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        t = (txt or "").strip()
        if t:
            out.append([round((min(xs) + max(xs)) / 2, 1),
                        round((min(ys) + max(ys)) / 2, 1), t])
    out.sort(key=lambda a: (a[1], a[0]))
    return out


def run(proj, pages, force=False):
    op = os.path.join(B, proj, '02_提取数据', 'OCR', '_xy.json')
    data = {}
    if os.path.exists(op) and not force:
        data = json.load(open(op, encoding='utf-8'))
    d0 = os.path.join(B, proj, '01_下载文档')
    fn = None
    for f in os.listdir(d0):
        if '发行说明书' in f and not any(k in f for k in ('更正', '复核', '变更')):
            fn = f
            break
    if not fn:
        print(f'{proj} 缺说明书')
        return
    todo = [p for p in pages if str(p) not in data]
    if not todo:
        print(f'{proj} 坐标已缓存 {len(data)} 页')
        return
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    doc = fitz.open(os.path.join(d0, fn))
    for pn in todo:
        if pn > doc.page_count:
            continue
        data[str(pn)] = ocr_page(ocr, doc, pn)
        print(f'  {proj} p{pn}  {len(data[str(pn)])} 框', flush=True)
        json.dump(data, open(op, 'w', encoding='utf-8', newline=''),
                  ensure_ascii=False)
    print(f'{proj} → {op} {os.path.getsize(op):,}B')


if __name__ == '__main__':
    JOBS = [
        ('兴瑞2021年第一期', list(range(108, 122))),
        ('兴瑞2023年第四期', list(range(104, 120))),
    ]
    for proj, pages in JOBS:
        run(proj, pages, force='--force' in sys.argv)
    print('XY COORD DONE')
