# -*- coding: utf-8 -*-
"""兴瑞 · 文本抽取 + 扫描件 OCR（兴业银行专用）

与建行建鑫那套的差别（都是看着实际文件定的）：

1. **文件名有两种体例**，同一批里混用：
   · 2021 一期：`兴瑞2021年第一期不良资产支持证券发行说明书.pdf`
     （品牌在前，类型在后，**不带日期**）
   · 其余各期：`发行说明书_兴瑞2023年第七期_20231204.pdf`
     （类型在前，品牌+日期在后）
   所以归类不能只按前缀，要两头都认。

2. ★★ **受托机构报告的文件名里没有「第N期」，只有出具日期**：
   `受托机构报告_兴业银行股份有限公司兴瑞2021年第一期_20210719.pdf`
   建行/招行/中信都是「…受托机构报告2021年第2期（总第5期）.pdf」，期号在名字里。
   兴瑞只能**按日期升序编号** TR01..TRnn —— 这也是唯一可靠的定号方式
   （同一年可能有多份，月份跨度不规则，不能按年月推）。

3. **评级报告两份，必须按机构分开**：
   · `信用评级报告及跟踪评级安排（中债资信）.pdf` —— 括号里明写
   · `信用评级报告_兴瑞2023年第七期_20231204.pdf` 与 `…_20231204_2.pdf`
     —— 名字里没有机构名，必须**读首页判定**（中债资信 / 中诚信 / 东方金诚）
   ★ 数据定源铁律：回收预测只认中债资信那份，另一份仅供参考、不作取数来源。

4. 清算资料：兴瑞多为 `清算审计报告_…_日期.pdf`，少数为 `清算专项复核说明_…`。

产出：
  <proj>/02_提取数据/文本/<KEY>.txt          有文本层的直取
  <proj>/02_提取数据/OCR/<KEY>.ocr.txt       扫描件的 OCR
  <proj>/02_提取数据/_text_index.json        文件 → KEY 映射与文本量

KEY 规则（与建行/招行/中信完全一致，便于共用下游脚本）：
  SM 说明书 / ZZ 中债资信评级 / XSJ 其他机构评级 / FXJG 发行结果
  XTGG 信托公告 / FXGG 发行公告 / FXBF 发行办法 / CLGG 成立公告
  CXT 承销团 / GZPJ 跟踪评级 / ZDSJ 重大事件
  TRnn 受托机构报告（按日期升序）
  LQAUDIT 清算审计报告 / LQREVIEW 清算专项复核说明 / LQ 其他清算件

用法：
  python 04_extract.py --proj "E:\\兴业银行兴瑞冒烟测试\\兴瑞2021年第二期"
  python 04_extract.py --proj ... --ocr --ocr-keys ZZ
"""
import argparse
import json
import os
import re
import sys
import time

import fitz

CN = "一二三四五六七八九十"


def _brand(fn):
    """从文件名里取出项目名（兴瑞YYYY年第N期），用于判定「是不是本项目」"""
    m = re.search(r"兴瑞(\d{4})年(?:第)?([一二三四五六七八九十\d]+)期", re.sub(r"\s+", "", fn))
    return m.group(0) if m else None


# ── 文件名 → KEY ─────────────────────────────────────────
def key_of(fn, base_dir=None):
    """返回 (KEY, 补充信息)

    KEY 可能带 TRnn 期号，此时要把同项目下所有受托报告的日期一起排序后编号，
    故 base_dir 传入项目名时用「全量文件名」列表来定号（见 assign_tr_keys）。
    单文件调用时 TR 先返回 ("TR?", 日期)，由 assign_tr_keys 统一改写。
    """
    base = os.path.splitext(fn)[0]
    b = re.sub(r"\s+", "", base)

    # ★ 先判「清算」，再判「受托报告」：
    #   「…受托机构报告…清算审计报告」这类合订本标题两种词都有，
    #   先匹配受托报告会把它归成 TRnn，清算数据整个取不到。
    if "清算" in b:
        if "复核" in b or "专项复核" in b:
            return "LQREVIEW", None
        if "审计" in b and "复核" not in b:
            return "LQAUDIT", None
        return "LQ", None

    if "受托机构报告" in b or "受托报告" in b or "受托机构报（" in b:
        # 年度/半年度专项复核说明不进 TR 序列
        if "复核" in b or "专项" in b or "审计报告" in b:
            return "TRREVIEW", None
        # ★ 期号不在文件名里，只能靠日期排序（见 assign_tr_keys）
        m = re.search(r"_(\d{8})$", b)
        return "TR?", (m.group(1) if m else None)

    # ★ 顺序关键：「信用评级报告**及跟踪评级安排**（中债资信）」是**发行时**的
    #   评级报告（末尾附跟踪评级安排说明），不是存续期跟踪评级报告。
    #   若先判「跟踪评级」，兴瑞 2021 一期两份定源评级会被整成 GZPJ，
    #   ZZ 缺失 → 回收预测取不到中债资信口径，评级交叉校验全空。
    #   判据：**以「跟踪评级报告」开头**的才是跟踪评级；含「信用评级」的一律算评级报告。
    if b.startswith("跟踪评级报告") or ("跟踪评级" in b and "信用评级" not in b):
        return "GZPJ", None
    if "承销团" in b:
        return "CXT", None
    if "发行结果" in b or "簿记建档" in b:
        return "FXJG", None
    if "发行说明书" in b or "发行说明" in b:
        return "SM", None
    if "重大事件" in b or "重大事项" in b:
        return "ZDSJ", None
    if "信托公告" in b or ("信托合同" in b):
        return "XTGG", None
    if "发行公告" in b:
        return "FXGG", None
    if "发行办法" in b or "申购" in b:
        return "FXBF", None
    if "成立公告" in b or "设立公告" in b:
        return "CLGG", None
    if "评级" in b:
        # 机构名可能在括号里（2021 一期），也可能完全没有（其余各期）
        # 先按括号/关键词判，判不出的留 "RAT?"，由 detect_rating_agency 读首页定
        if "中债" in b:
            return "ZZ", None
        for k in ("中诚信", "东方金诚", "新世纪", "联合", "标普", "惠誉", "穆迪"):
            if k in b:
                return "XSJ", k
        return "RAT?", None
    return "OTHER", None


def assign_tr_keys(items, pages_dir):
    """把 TR? 按日期升序改成 TR01..TRnn

    items: [(fn, key, extra)]；返回新列表
    ★ 同日多份时用文件名兜底排序，保证结果稳定可复现（G1 的前提）。
    """
    trs = [(fn, ex) for fn, k, ex in items if k == "TR?"]
    if not trs:
        return items
    # 日期取不到时退回文件的 mtime 不可靠（拷贝会变），故必须要求在文件名里；
    # 取不到的直接报错让人补，不静默猜。
    missing = [fn for fn, ex in trs if not ex]
    if missing:
        raise SystemExit("受托机构报告缺日期，无法定期号：" + str(missing[:3]))
    trs.sort(key=lambda x: (x[1], x[0]))
    mapping = {fn: f"TR{i:02d}" for i, (fn, _) in enumerate(trs, 1)}
    out = []
    for fn, k, ex in items:
        out.append((fn, mapping.get(fn, k), ex))
    return out


# 机构判定的首页关键词（OCR 或文本层均可）
# ★★ 顺序与写法都被实战坑过，不能随意改：
#   ① 标普信评的网址是 `spgchinaratings.cn`，**含子串 "chinaratings"**。
#      原来把 "chinaratings" 当「中债资信」的判据，于是标普那份被认成中债资信
#      （兴瑞2022一期实测：24 页那份实为标普信评，36 页才是中债资信），
#      定源判错 → 直接用错机构的回收预测。
#   ② 故中债资信只用中文「中债资信」＋专属域名 `chinaratings.com.cn`，
#      且标普必须排在前面先匹配掉。
#   ③ 中诚信的 `ccxi` 要带点号上下文（`ccxi.com.cn`），避免撞其他串。
_AGENCY = [
    ("标普信评", ("标普信评", "spgchinaratings", "s&pglobalchinaratings")),
    ("中债资信", ("中债资信", "chinaratings.com.cn", "chinabondrating")),
    ("中诚信", ("中诚信", "ccxi.com.cn", "ccxi-")),
    ("东方金诚", ("东方金诚", "dfjc.com.cn")),
    ("联合资信", ("联合资信", "lianhe.com.cn")),
    ("新世纪", ("新世纪资信",)),
    # 兴瑞 2024 三期实测：参考评级由「惠誉博华」出具（Fitch Bohua，页眉写 FitchBohua）
    ("惠誉博华", ("惠誉博华", "fitchbohua", "fitch bohua")),
    ("穆迪", ("穆迪", "moody")),
]


def detect_rating_agency(pdf):
    """读前 3 页判定评级机构，返回机构名或 None

    ★ 为什么必须读内容：兴瑞除 2021 一期外，评级文件名**不含机构名**
      （`信用评级报告_兴瑞2023年第七期_20231204.pdf` 与 `…_2.pdf`），
      只能靠首页抬头/声明判定。判错会直接把联合/中诚信的数据当定源用，
      违反「回收预测只认中债资信」这条铁律。
    """
    try:
        doc = fitz.open(pdf)
    except Exception:
        return None
    txt = ""
    for i in range(min(3, doc.page_count)):
        txt += doc[i].get_text()
    low = re.sub(r"\s+", "", txt).lower()
    if len(low) < 30:
        # 扫描件：直接 OCR 首页
        try:
            import numpy as np
            from rapidocr_onnxruntime import RapidOCR
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72))
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = img[:, :, :3]
            res, _ = RapidOCR()(img)
            low = re.sub(r"\s+", "", "".join(x[1] for x in (res or []))).lower()
        except Exception:
            return None
    for name, keys in _AGENCY:
        if any(k.lower() in low for k in keys):
            return name
    return None


# ── 文本抽取 ─────────────────────────────────────────────
def _cjk_ratio(t):
    if not t:
        return 0.0
    good = len(re.findall(r"[\u4e00-\u9fa5（）：；，。、《》]", t))
    return good / max(len(t), 1)


def extract_text(pdf):
    """抽取文本，并识别「伪文本层」（字体未嵌入 → 提取出来是乱码）"""
    doc = fitz.open(pdf)
    pages, empty, garbled = [], 0, 0
    for i in range(doc.page_count):
        t = doc[i].get_text().strip()
        if len(t) < 20:
            empty += 1
        elif _cjk_ratio(t) < 0.10:
            garbled += 1
        pages.append(t)
    eff_empty = empty + (garbled if garbled > doc.page_count * 0.8 else 0)
    return pages, eff_empty, doc.page_count, garbled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proj", required=True)
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--keys", default="")
    ap.add_argument("--ocr-keys", default="")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--pages", default="")
    ap.add_argument("--probe-only", action="store_true",
                    help="只打印键位映射，不写文件（先核对再跑）")
    a = ap.parse_args()

    src = os.path.join(a.proj, "01_下载文档")
    out = os.path.join(a.proj, "02_提取数据")
    tdir = os.path.join(out, "文本")
    odir = os.path.join(out, "OCR")
    os.makedirs(tdir, exist_ok=True)
    os.makedirs(odir, exist_ok=True)

    pdfs = sorted(f for f in os.listdir(src) if f.lower().endswith(".pdf"))
    items = [(fn, *key_of(fn)) for fn in pdfs]
    items = assign_tr_keys(items, src)

    # 评级报告：名字判不出机构的，读首页定
    fixed = []
    for fn, k, ex in items:
        if k == "RAT?":
            ag = detect_rating_agency(os.path.join(src, fn))
            if ag == "中债资信":
                k = "ZZ"
            elif ag:
                k = "XSJ"
            else:
                k = "XSJ"          # 判不出时归到"参考"而非定源，宁可不用也不误用
            fixed.append((fn, k, ag or "未判定"))
        else:
            fixed.append((fn, k, ex))
    items = fixed

    bykey = {}
    for fn, k, ex in items:
        bykey.setdefault(k, []).append(fn)

    if a.probe_only:
        print(f"{'KEY':10s}{'机构/备注':12s}文件")
        for k in sorted(bykey):
            for fn in bykey[k]:
                ex = next((e for f2, k2, e in items if f2 == fn), None)
                print(f"{k:10s}{str(ex or ''):12s}{fn}")
        return 0

    want = set(x.strip() for x in a.keys.split(",") if x.strip())
    ocr_want = set(x.strip() for x in a.ocr_keys.split(",") if x.strip())

    # OCR 白名单：这些类型要取数；承销团/重大事件/年度复核不取数，不浪费 OCR
    OCR_NEEDED = ("ZZ", "FXJG", "LQREVIEW", "LQAUDIT", "CLGG", "LQ")
    OCR_SKIP_PREFIX = ("TRUNK", "TRYEAR", "TRREVIEW")

    idx, ocr_jobs = [], []
    for k in sorted(bykey, key=lambda x: (len(x), x)):
        fns = bykey[k]
        if want and k not in want:
            continue
        # 同键多份：优先体积最大的（通常是主册）；_2 这类副本跳过
        fns.sort(key=lambda f: -os.path.getsize(os.path.join(src, f)))
        fn = fns[0]
        p = os.path.join(src, fn)
        pages, empty, npg, garbled = extract_text(p)
        txt = "\n\n".join(f"<<<PAGE {i+1}>>>\n{pages[i]}" for i in range(npg))
        rec = {"key": k, "file": fn, "pages": npg, "n_empty": empty,
               "n_garbled": garbled, "chars": len("".join(pages)), "others": fns[1:]}
        if empty == npg:
            if (k in OCR_NEEDED or k.startswith("TR")) and not k.startswith(OCR_SKIP_PREFIX):
                ocr_jobs.append((k, p, npg))
                rec["mode"] = "ocr-needed"
            else:
                rec["mode"] = "ocr-skip"
        elif empty > npg * 0.5:
            if (k in OCR_NEEDED or k.startswith("TR")) and not k.startswith(OCR_SKIP_PREFIX):
                ocr_jobs.append((k, p, npg))
            rec["mode"] = "ocr-partial"
            open(os.path.join(tdir, f"{k}.txt"), "w", encoding="utf-8",
                 newline="").write(txt)
        else:
            rec["mode"] = "text"
            open(os.path.join(tdir, f"{k}.txt"), "w", encoding="utf-8",
                 newline="").write(txt)
        idx.append(rec)

    json.dump(idx, open(os.path.join(out, "_text_index.json"), "w", encoding="utf-8",
                        newline=""), ensure_ascii=False, indent=1)

    print(f"{'KEY':10s}{'页':>5}{'空页':>6}{'乱码':>5}{'字数':>9}  模式  文件")
    for r in idx:
        print(f"{r['key']:10s}{r['pages']:>5}{r['n_empty']:>6}{r.get('n_garbled', 0):>5}"
              f"{r['chars']:>9}  {r['mode']:12s} {r['file'][:46]}")

    if not a.ocr:
        if ocr_jobs:
            print(f"\n需 OCR 的 {len(ocr_jobs)} 份：{[k for k, _, _ in ocr_jobs]}")
            print("加 --ocr 执行")
        return 0

    todo = [x for x in ocr_jobs if (not ocr_want or x[0] in ocr_want)]
    if not todo:
        print("\n无需 OCR")
        return 0
    from rapidocr_onnxruntime import RapidOCR
    import numpy as np
    ocr = RapidOCR()
    print(f"\n开始 OCR {len(todo)} 份（dpi={a.dpi}）")
    for k, p, npg in todo:
        op = os.path.join(odir, f"{k}.ocr.txt")
        prev = {}
        if os.path.exists(op) and os.path.getsize(op) > 200:
            _old = open(op, encoding="utf-8").read()
            for _m in re.finditer(r"<<<PAGE (\d+)>>>(.*?)(?=<<<PAGE|\Z)", _old, re.S):
                prev[int(_m.group(1))] = _m.group(2)
        if os.path.exists(op) and os.path.getsize(op) > 500 and not a.force and not a.pages:
            print(f"  {k}: 已存在，跳过（--force 可重做）")
            continue
        doc = fitz.open(p)
        t0, chunks = time.time(), []
        keep = None
        if a.pages:
            keep = set()
            for part in a.pages.split(","):
                part = part.strip()
                if "-" in part:
                    lo, hi = part.split("-")
                    keep |= set(range(int(lo), int(hi) + 1))
                elif part:
                    keep.add(int(part))
        for i in range(doc.page_count):
            if keep is not None and (i + 1) not in keep and (i + 1) in prev:
                chunks.append(f"<<<PAGE {i+1}>>>\n{prev[i+1]}")
                continue
            if keep is not None and (i + 1) not in keep:
                if (i + 1) in prev:
                    chunks.append(f"<<<PAGE {i+1}>>>\n{prev[i+1]}")
                continue
            pix = doc[i].get_pixmap(matrix=fitz.Matrix(a.dpi / 72, a.dpi / 72))
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = img[:, :, :3]
            res, _ = ocr(img)
            body = "\n".join(x[1] for x in (res or []))
            chunks.append(f"<<<PAGE {i+1}>>>\n{body}")
        open(op, "w", encoding="utf-8", newline="").write("\n\n".join(chunks))
        print(f"  {k}: {doc.page_count} 页 / {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
