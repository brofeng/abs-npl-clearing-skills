# -*- coding: utf-8 -*-
"""扫描版说明书的分布章节：坐标 OCR + 按行还原

★ 为什么需要它：
  扫描件走普通 OCR 时，输出是「按文本框先后」排列的，表格的行列会被打散 ——
  实测兴瑞2021一期 p109：
        标签批：60万元以上 / (0,5] / (5,10] / (10,15] / (20,30) / (30,60) / (15,20) / 总计
        数字批：201,602 / 13,831 / 3,433 / 220,617 / 911 / 537 / 274 / 29
  两批都乱序，按顺序配对所有维度都会错位，而且错得很像样（合计照样对得上）。
  唯一稳的做法是拿 OCR 的**框坐标**按 y 聚行、按 x 排序，还原成
        (0,5] | 201,602 | 91.38 | 347,393.07 | 66.03 | ...
  再交给下游按普通文本解析。

产物写成 02_提取数据/OCR/SM.xy.txt，03_parse_dist 优先读它（只覆盖分布章节页）。
"""
import os
import re
import sys

import fitz
import numpy as np

B = r'E:/兴业银行兴瑞冒烟测试'
S = os.path.join(B, '脚本')
sys.path.insert(0, S)

DPI = 250          # 表格要看清千分位，150 会糊
Y_TOL = 16         # 同一行的 y 容差（250dpi 下正文行高约 30px）


def rows_from_ocr(res):
    """把 rapidocr 的框还原成行：[(y, [(x, text), ...]), ...] → ["a | b | c", ...]"""
    items = []
    for box, txt, _score in (res or []):
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        items.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, txt.strip()))
    items.sort(key=lambda t: (t[1], t[0]))
    rows, cur, cur_y = [], [], None
    for _xc, yc, txt in items:
        if cur_y is None or abs(yc - cur_y) <= Y_TOL:
            cur.append((_xc, txt))
            cur_y = yc if cur_y is None else (cur_y * (len(cur) - 1) + yc) / len(cur)
        else:
            rows.append((cur_y, cur))
            cur, cur_y = [( _xc, txt)], yc
    if cur:
        rows.append((cur_y, cur))
    out = []
    for _y, cells in rows:
        cells.sort(key=lambda t: t[0])
        out.append(" | ".join(t for _x, t in cells if t))
    return out


def run(proj, pages, out_name='SM.xy.txt', force=False):
    op = os.path.join(B, proj, '02_提取数据', 'OCR', out_name)
    if os.path.exists(op) and os.path.getsize(op) > 500 and not force:
        print(f'{proj} {out_name} 已存在，跳过（--force 重做）')
        return
    fn = None
    d0 = os.path.join(B, proj, '01_下载文档')
    for f in os.listdir(d0):
        if '发行说明书' in f and not any(k in f for k in ('更正', '复核', '变更')):
            fn = f
            break
    if not fn:
        print(f'{proj} 缺说明书')
        return
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    doc = fitz.open(os.path.join(d0, fn))
    chunks = []
    for pn in pages:
        if pn > doc.page_count:
            continue
        pix = doc[pn - 1].get_pixmap(matrix=fitz.Matrix(DPI / 72, DPI / 72))
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        res, _ = ocr(img)
        body = "\n".join(rows_from_ocr(res))
        chunks.append(f"<<<PAGE {pn}>>>\n{body}")
        print(f'  {proj} p{pn}  {len(rows_from_ocr(res))} 行', flush=True)
    with open(op, 'w', encoding='utf-8', newline='') as f:
        f.write("\n\n".join(chunks))
    print(f'{proj} → {op} {os.path.getsize(op):,}B')


if __name__ == '__main__':
    # 分布章节页（含表头在第 8 章开头前 2 页）
    JOBS = [
        ('兴瑞2021年第一期', list(range(108, 122))),
        ('兴瑞2023年第四期', list(range(104, 120))),
    ]
    for proj, pages in JOBS:
        run(proj, pages, force='--force' in sys.argv)
    print('XY OCR DONE')
