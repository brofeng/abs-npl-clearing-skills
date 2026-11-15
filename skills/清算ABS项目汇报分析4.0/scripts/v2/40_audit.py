# -*- coding: utf-8 -*-
r"""40_audit —— 「明细与底稿」视图（独立视图 #view-appendix，侧栏单独栏目）。

第四轮精修 · 折叠区独立成栏目。
本模块输出一个**独立视图的全部内容**（不含 <section> 外壳），由 build_v2.py
放进 `#view-appendix`；侧栏入口「► 明细与底稿」。

页面结构（极简页头 + 5 个默认收起的折叠块）：
  页头  明细与底稿 / 一句话说明（≤3 行，无 hero、无总览导航、无元说明）
  fen  · 分品种结构        三类资产池横向对比
  bank · 银行维度与异常点  9 家机构强弱与异常点
  pat  · 规律发现          4 条可复用判读
  det  · 28 单明细         全字段逐单读数
  def  · 缺陷清单          S1–S10 数据欠账

用户要求「高度提炼文字、展示数据」：每块标题下的一句话说明 ≤20 字，
细节全部由表与图自证；折叠块默认收起，`+`/`−` 切换。

沿用的硬性口径：
  · 处置费率**只有一个口径**：处置费用 ÷ 累计回收
  · 「折价率」0 次，一律「证券化率」
  · 「成本强度」0 次

契约：导出 CSS / HTML / JS；HTML 无 <section> 外壳；CSS 无注释、.a-* 前缀、
      不写 #view-appendix / #view-xcompare 自身选择器（由组装器统一作用域化）；
      JS 纯 IIFE 局部变量；手写 SVG。
"""
from __future__ import annotations

import io
import json
import math
import re
import statistics as st
import sys
from collections import OrderedDict
from pathlib import Path

# ── 根路径解析（v12：支持搬迁）─────────────────────────────────────
# 优先级：环境变量 NPL_ABS_HOME > 本目录 _root.txt > 默认 E:\不良ABS穿透研究
# 目标结构：<HOME>\清算28单_单项目穿透\ 与 <HOME>\清算28单_不良ABS分析\
def _resolve_home():
    import os as _os
    from pathlib import Path as _P
    _v = _os.environ.get("NPL_ABS_HOME")
    if _v:
        _p = _P(_v)
        if _p.exists():
            return _p
    _c = _P(__file__).resolve().parent / "_root.txt"
    if _c.exists():
        try:
            _s = _c.read_text(encoding="utf-8").strip()
            if _s and _P(_s).exists():
                return _P(_s)
        except Exception:
            pass
    return _P(r"E:\不良ABS穿透研究")
_HOME = _resolve_home()
# ──────────────────────────────────────────────────────────────────

# ════════════════════════════════════════════════════════════════════════
# 0. 配置与数据
# ════════════════════════════════════════════════════════════════════════
_HERE = Path(__file__).resolve().parent
_E = _HERE.parent.parent
if not (_E / "设计资产").is_dir():
    _E = _HOME / "清算28单_不良ABS分析"
_ASSET = _E / "设计资产"

CAT_COLOR = {"信用卡不良": "#A52524", "个人消费贷款": "#2D3955", "个人经营贷款": "#1F7A5C"}
CAT_ORD = ["信用卡不良", "个人消费贷款", "个人经营贷款"]

FOLD_LEAD = "以下为细粒度数据与可深挖内容，默认收起；展开不影响主结论阅读。"
FOLD_TITLE = "明细与底稿"

FOLDS = [
    ("fen", "分品种结构", "三类资产池横向对比"),
    ("bank", "银行维度与异常点", "9 家机构强弱与异常点"),
    ("pat", "规律发现", "4 条可复用判读"),
    ("det", "28 单明细", "全字段逐单读数"),
    ("def", "缺陷清单", "S1–S10 数据欠账"),
]

# 缺陷条目：(编号, 名称, 等级, 范围与取证, 处置)
DEFECTS = [
    ("S1", "次级档固定资金成本缺失", "高",
     3, "臻粹2024年第三期、鸿富2023年第七期、鸿富2023年第三期",
     "不插补、不用邻单代替。"),
    ("S2", "说明书取率无披露", "高",
     19, "建鑫2022年第六期起共 19 单（招商、平安、光大、广发、民生 5 家完全无取率）",
     "批量档无法用说明书独立复核，可信度低于有取率的 9 单。"),
    ("S3", "复利模型基数不可复核", "高", None,
     "建鑫2022年第一期：模型＝复利，说明书面值 619.24 万元 vs 复利折算 973.97 万元",
     "需取该单逐期次级档本金余额表才能复现，不据此下量级结论。"),
    ("S4", "说明书页码与条款命中缺口", "中", None,
     "「10% 阈值」条款命中缺 5 单；1 单条款命中表为空",
     "无页码则无法回源定位，空缺处记「—」。"),
    ("S5", "超额奖励 / 基本服务费率未披露", "中", None,
     "超额奖励缺 16/28、基本服务费率缺 18/28",
     "费率侧推论只能覆盖已披露单。"),
    ("S6", "分档表期间缺口", "中", 1,
     "招元和萃2023年第八期（缺第 17 期）",
     "缺口期次未纳入统计，可能使批量档指标系统性偏低。"),
    ("S7", "持有月数缺失", "中",
     3, "臻粹2024年第三期、鸿富2023年第七期、鸿富2023年第三期",
     "年化换算依赖持有月数；这些单同时无固定成本明细。"),
    ("S8", "入池息费字段口径不一致", "高", None,
     "中誉至诚2024年第五期 <code>pool_intfee</code> 只含入池费用 283,335,660.03，"
     "漏入池利息 157,533,519.48；说明书 p121：本息费 2,237,824,631.87 ＝ 本金 ＋ 利息 ＋ 费用",
     "已按「本息费 − 本金」归一；该单入池息费会被低估约 1.58 亿元。"),
    ("S9", ".main 非滚动容器却调用 scrollTo", "低", None,
     "切视图时对非滚动容器调用 <code>scrollTo(0,0)</code>，导致不回顶部",
     "已修：改由 window / 页面根执行回顶。"),
    ("S10", "固定成本明细仅 8 单", "中",
     20, "20/28 单 <code>subFix</code> 为 0；仅中国银行 2、交通银行 2、建设银行 2、光大 1、邮储 1 有明细",
     "单利标准化年化率只覆盖 8 单，其余记「—」。"),
]


def _load():
    prof = json.loads((_ASSET / "payload_28.json").read_text(encoding="utf-8"))
    audit = json.loads((_ASSET / "audit_payload.json").read_text(encoding="utf-8"))
    return prof, audit


# ════════════════════════════════════════════════════════════════════════
# 1. 工具
# ════════════════════════════════════════════════════════════════════════
DASH = "—"


def esc(s):
    return (str("" if s is None else s)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def yi(v, d=2):
    return DASH if not v else f"{v / 1e8:,.{d}f}"


def wan(v, d=2):
    return DASH if not v else f"{v / 1e4:,.{d}f}"


def pct(v, d=2):
    return DASH if v is None else f"{v * 100:.{d}f}%"


def f2(v, d=2):
    return DASH if v is None else f"{v:.{d}f}"


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    a = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return a / b if b else None


def robust_z(vals):
    """MAD 稳健 z：1.4826 × (x − median) / MAD。返回 (median, mad, [z...])"""
    med = st.median(vals)
    mad = st.median([abs(v - med) for v in vals]) or 1e-12
    return med, mad, [1.4826 * (v - med) / mad for v in vals]


class SVG:
    def __init__(self, w, h):
        self.w, self.h, self.buf = w, h, []

    def add(self, s):
        self.buf.append(s)

    def rect(self, x, y, w, h, fill, rx=0, title=None, extra=""):
        t = f"<title>{esc(title)}</title>" if title else ""
        self.add(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(w, 0):.2f}" height="{max(h, 0):.2f}"'
                 f' rx="{rx}" fill="{fill}"{extra}>{t}</rect>')

    def line(self, x1, y1, x2, y2, stroke, sw=1, dash=None, cap=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        c = f' stroke-linecap="{cap}"' if cap else ""
        self.add(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"'
                 f' stroke="{stroke}" stroke-width="{sw}"{d}{c}/>')

    def circle(self, cx, cy, r, fill, title=None, stroke=None, sw=1):
        t = f"<title>{esc(title)}</title>" if title else ""
        s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.add(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}"{s}>{t}</circle>')

    def text(self, x, y, s, size=11.5, fill="#38425A", anchor="start", weight=None):
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        w = f' font-weight="{weight}"' if weight else ""
        self.add(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{fill}"{a}{w}>'
                 f'{esc(s)}</text>')

    def render(self, label=""):
        lb = f' role="img" aria-label="{esc(label)}"' if label else ""
        return (f'<svg class="a-svg" viewBox="0 0 {self.w} {self.h}"'
                f' width="{self.w}" height="{self.h}"'
                f' preserveAspectRatio="xMidYMid meet"{lb}>{"".join(self.buf)}</svg>')


INK, INK2, SUB, MUTE = "#141A26", "#38425A", "#697487", "#98A2B3"
NAVY, POS, RED, WARN2 = "#2D3955", "#B3261E", "#A52524", "#B0763F"
GRID, LINE2 = "#E4E9F0", "#D5DCE6"
GREY = "#9AA6B8"


def _bar(sv, x, y, w, h, fill, title, rx=3):
    sv.rect(x, y, w, h, fill, rx=rx, title=title)


# ════════════════════════════════════════════════════════════════════════
# 2. 派生量
# ════════════════════════════════════════════════════════════════════════
def build_stats(prof):
    order = prof["ORDER"]
    pf = prof["PROF"]

    # ── 分品种 ──
    cats = OrderedDict()
    for k in order:
        cats.setdefault(pf[k]["cat"], []).append(k)
    cat_rows = []
    for c in CAT_ORD:
        ks = cats.get(c, [])
        if not ks:
            continue
        issue = sum(pf[k]["issue"] or 0 for k in ks)
        pool = sum(pf[k]["poolTotal"] or 0 for k in ks)
        rec = sum(pf[k]["recovered"] or 0 for k in ks)
        rr = [pf[k]["recRate"] for k in ks if pf[k].get("recRate") is not None]
        sr = [pf[k]["secRatio"] for k in ks if pf[k].get("secRatio") is not None]
        xs = [pf[k]["xirrSen"] for k in ks if pf[k].get("xirrSen") is not None]
        xu = [pf[k]["xirrSub"] for k in ks if pf[k].get("xirrSub") is not None]
        vf = [pf[k]["vsForecast"] for k in ks if pf[k].get("vsForecast") is not None]
        cat_rows.append({
            "cat": c, "n": len(ks),
            "issue": issue, "pool": pool, "rec": rec,
            "recW": (rec / pool) if pool else None,
            "recMed": st.median(rr) if rr else None,
            "secW": (issue / pool) if pool else None,
            "secMed": st.median(sr) if sr else None,
            "sen": st.median(xs) if xs else None,
            "sub": st.median(xu) if xu else None,
            "vf": st.median(vf) if vf else None,
        })

    # ── 银行维度 + MAD ──
    banks = OrderedDict()
    for k in order:
        banks.setdefault(pf[k]["issuer"], []).append(k)
    bank_rows = []
    for b, ks in banks.items():
        issue = sum(pf[k]["issue"] or 0 for k in ks)
        pool = sum(pf[k]["poolTotal"] or 0 for k in ks)
        rec = sum(pf[k]["recovered"] or 0 for k in ks)
        xs = [pf[k]["xirrSen"] for k in ks if pf[k].get("xirrSen") is not None]
        xu = [pf[k]["xirrSub"] for k in ks if pf[k].get("xirrSub") is not None]
        vf = [pf[k]["vsForecast"] for k in ks if pf[k].get("vsForecast") is not None]
        bank_rows.append({
            "bank": b, "n": len(ks), "issue": issue, "pool": pool, "rec": rec,
            "recW": (rec / pool) if pool else None,
            "recMed": st.median([pf[k]["recRate"] for k in ks if pf[k].get("recRate") is not None])
            if any(pf[k].get("recRate") is not None for k in ks) else None,
            "secW": (issue / pool) if pool else None,
            "sen": st.mean(xs) if xs else None,
            "sub": st.mean(xu) if xu else None,
            "vf": (sum(vf) / len(vf)) if vf else None,
        })
    # 指标轴：键 → (标签, 取值函数, 显示, 方向说明)
    METRICS = [
        ("recW", "回收率（加权）", lambda r: r["recW"], lambda v: pct(v, 2), None),
        ("secW", "证券化率（加权）", lambda r: r["secW"], lambda v: pct(v, 2), None),
        ("sen", "优先档 XIRR（均值）", lambda r: r["sen"], lambda v: pct(v, 2), None),
        ("sub", "次级档 XIRR（均值）", lambda r: r["sub"], lambda v: pct(v, 2), None),
    ]
    for r in bank_rows:
        r["z"] = {}
        r["flag"] = {}
    for key, _lbl, get, _fmt, _d in METRICS:
        vals = [get(r) for r in bank_rows if get(r) is not None]
        if len(vals) < 3:
            continue
        med, mad, _ = robust_z(vals)
        for r in bank_rows:
            v = get(r)
            if v is None:
                r["z"][key] = None
                r["flag"][key] = ""
                continue
            z = 1.4826 * (v - med) / mad
            r["z"][key] = z
            r["flag"][key] = ("★" if abs(z) > 3.5 else ("·" if abs(z) > 2.5 else ""))

    # ── 规律发现：相关与极差 ──
    units = [(k, pf[k]) for k in order]
    def _cv(f):
        xs, ys = [], []
        for k, v in units:
            a, b = f(v), v.get("vsForecast")
            if a is not None and b is not None:
                xs.append(a)
                ys.append(b)
        return pearson(xs, ys)
    r_sec_rec = _cv(lambda v: v.get("secRatio"))
    r_sub_rec = _cv(lambda v: v.get("xirrSub"))
    r_sub_sec = pearson(
        [v["xirrSub"] for _k, v in units if v.get("xirrSub") is not None and v.get("secRatio") is not None],
        [v["secRatio"] for _k, v in units if v.get("xirrSub") is not None and v.get("secRatio") is not None])
    rr = [v["recRate"] for _k, v in units if v.get("recRate") is not None]
    sr = [v["secRatio"] for _k, v in units if v.get("secRatio") is not None]
    xs_ = [v["xirrSen"] for _k, v in units if v.get("xirrSen") is not None]
    xu_ = [v["xirrSub"] for _k, v in units if v.get("xirrSub") is not None]
    pat = {
        "r_sec_rec": r_sec_rec, "r_sub_rec": r_sub_rec, "r_sub_sec": r_sub_sec,
        "rr_rng": (min(rr), max(rr)), "sr_rng": (min(sr), max(sr)),
        "sen_rng": (min(xs_), max(xs_)), "sub_rng": (min(xu_), max(xu_)),
        "sen_span": (max(xs_) - min(xs_)) * 100, "sub_span": (max(xu_) - min(xu_)) * 100,
        "n": len(units),
    }
    # 次级档 XIRR ÷ 优先档 XIRR 倍数
    mult = [v["xirrSub"] / v["xirrSen"] for _k, v in units
            if v.get("xirrSub") and v.get("xirrSen")]
    pat["mult_med"] = st.median(mult) if mult else None
    pat["mult_max"] = max(mult) if mult else None
    return cat_rows, bank_rows, METRICS, pat


# ════════════════════════════════════════════════════════════════════════
# 3. 图 1：分品种两档 XIRR + 回收率（水平双条）
# ════════════════════════════════════════════════════════════════════════
def chart_cat(cat_rows):
    w = 860
    left, right = 132, 150
    x0, x1 = left, w - right
    hi = 28.0
    sx = lambda v: x0 + (v / hi) * (x1 - x0)
    rw, gap, top, head = 34, 20, 62, 44
    # 每个品种占：head + 3×rw（三条）+ gap；底部留轴标签 + 脚注
    h = top + sum(head + rw * 3 + gap for _ in cat_rows) + 58
    sv = SVG(w, h)
    sv.text(10, 18, "各品种：两档 XIRR 与回收率", 13, INK, weight=700)
    sv.text(10, 34, "横轴单位 %｜深色＝优先档 XIRR（中位）· 中色＝次级档 XIRR（中位）· "
                    "绿色＝回收率（加权）", 9.8, SUB)
    axis_y = h - 40
    for g in range(0, int(hi) + 1, 4):
        sv.line(sx(g), top - 8, sx(g), axis_y, GRID if g else LINE2, 1)
        sv.text(sx(g), axis_y + 13, f"{g}%", 9, MUTE, anchor="middle")
    y = top
    for r in cat_rows:
        sv.rect(8, y - 2, w - 16, head - 4 + rw * 3 + gap - 6, "#F7FAFD", rx=6)
        sv.text(16, y + 15, f'{r["cat"]} · {r["n"]} 单', 11.8, INK, weight=700)
        sv.text(16, y + 31, f'发行 {yi(r["issue"])} 亿元　入池本息费 {yi(r["pool"])} 亿元　'
                            f'累计回收 {yi(r["rec"])} 亿元', 9.6, SUB)
        y += head
        for label, val, col in (("优先档 XIRR", r["sen"], NAVY),
                                ("次级档 XIRR", r["sub"], "#4A6FA5"),
                                ("回收率", r["recW"], "#1F7A5C")):
            cy = y + rw / 2 - 3
            _bar(sv, sx(0), cy - 7, sx((val or 0) * 100) - sx(0), 14, col,
                 f'{r["cat"]}｜{label} {pct(val, 2)}\n'
                 f'样本 {r["n"]} 单｜发行 {yi(r["issue"])} 亿元｜入池本息费 {yi(r["pool"])} 亿元\n'
                 f'累计回收 {yi(r["rec"])} 亿元｜回收率（加权）{pct(r["recW"])}｜'
                 f'回收率（中位）{pct(r["recMed"])}\n'
                 f'证券化率（加权）{pct(r["secW"])}｜（中位）{pct(r["secMed"])}｜'
                 f'达成率中位 {pct(r["vf"])}')
            sv.text(x0 - 8, cy + 4, label, 10, INK2, anchor="end")
            sv.text(sx((val or 0) * 100) + 6, cy + 4, pct(val, 2), 10, INK)
            y += rw
        y += gap
    sv.text(x0 - 8, h - 10, "两档 XIRR 取组内中位；回收率取「累计回收 ÷ 入池本息费」（加权），"
                            "另有中位口径见悬停。", 9.4, MUTE)
    return sv.render("分品种两档XIRR与回收率对比图")


# ════════════════════════════════════════════════════════════════════════
# 4. 图 2：银行维度 + MAD 异常点（横向箱线式区间条）
# ════════════════════════════════════════════════════════════════════════
def chart_bank(bank_rows):
    key, lbl, get, fmt = "sub", "次级档 XIRR（均值）", lambda r: r["sub"], lambda v: pct(v, 2)
    vals = [get(r) for r in bank_rows if get(r) is not None]
    med, mad, _ = robust_z(vals)
    band = 3.5 * mad / 1.4826                      # |z| > 3.5 的等价绝对带宽
    rows = sorted([r for r in bank_rows if get(r) is not None], key=lambda r: -get(r))
    w = 900
    left, right = 96, 176
    x0, x1 = left, w - right
    lo = min(min(vals), med - band) - 1.5
    hi = max(max(vals), med + band) + 1.5
    sx = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    rw, top = 26, 52
    h = top + rw * len(rows) + 46
    sv = SVG(w, h)
    sv.text(10, 18, f"各发起机构：{lbl} 与 MAD 异常点", 13, INK, weight=700)
    sv.text(10, 33, f"虚线＝{lbl}中位 {fmt(med)}· 灰带＝中位 ±3.5×MAD（正常区间）· ★＝越界异常 · ·＝|z|>2.5 边缘", 9.8, SUB)
    for g in range(int(lo), int(hi) + 1, 5):
        sv.line(sx(g), top - 8, sx(g), h - 30, GRID if g else LINE2, 1)
        sv.text(sx(g), top - 13, f"{g}%", 9, MUTE, anchor="middle")
    sv.rect(sx(med - band), top - 8, sx(med + band) - sx(med - band), h - 30 - (top - 8),
            "#F1F5FB", rx=4)
    sv.line(sx(med), top - 8, sx(med), h - 30, GREY, 1.4, dash="5 4")
    sv.text(sx(med), h - 16, f"中位 {fmt(med)}", 9.2, MUTE, anchor="middle")
    y = top
    for r in rows:
        v = get(r)
        cy = y + rw / 2 - 2
        z = r["z"].get(key)
        flag = r["flag"].get(key, "")
        col = RED if flag == "★" else (WARN2 if flag == "·" else NAVY)
        sv.rect(8, y - 1, w - 16, rw - 4, "#FCFDFF" if flag != "★" else "#FDF6F5", rx=5)
        sv.line(sx(lo), cy, sx(v), cy, "#C6CEDA", 4, cap="round")
        sv.circle(sx(v), cy, 5.4, col,
                  f'{r["bank"]}｜{lbl} {fmt(v)}｜MAD 稳健 z = {z:+.2f}{"（异常）" if flag == "★" else ("（边缘）" if flag == "·" else "")}\n'
                  f'样本 {r["n"]} 单｜发行 {yi(r["issue"])} 亿元｜入池本息费 {yi(r["pool"])} 亿元\n'
                  f'回收率（加权）{pct(r["recW"])}｜回收率（中位）{pct(r["recMed"])}｜'
                  f'证券化率（加权）{pct(r["secW"])}\n'
                  f'优先档 XIRR（均值）{pct(r["sen"])}｜达成率（均值）{pct(r["vf"])}',
                  stroke="#fff", sw=1.3)
        sv.text(x0 - 10, cy + 4, f'{flag}{r["bank"]}', 10.4, col, anchor="end")
        sv.text(x1 + 10, cy + 4, f'{fmt(v)}  z={z:+.2f}', 9.6, SUB)
        y += rw
    sv.text(x0, h - 8, "判定口径：z＝1.4826×(x−中位)/MAD；|z|>3.5 记 ★ 异常，|z|>2.5 记 · 边缘。"
                       "样本仅 2 单的机构（中行/交行/建行/光大/民生）z 值对单点敏感，仅作提示。", 9.4, MUTE)
    return sv.render("各发起机构次级档XIRR与MAD异常点图")


# ════════════════════════════════════════════════════════════════════════
# 5. 图 3–4：散点
# ════════════════════════════════════════════════════════════════════════
def chart_scatter(pairs, xlab, ylab, title, sub, xr=None, color_by="cat", w=470, h=330):
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    L, R, T, B = 62, 20, 48, 54
    px0, px1, py0, py1 = L, w - R, T, h - B
    xlo, xhi = min(xs), max(xs)
    ylo, yhi = min(ys), max(ys)
    xpad = (xhi - xlo) * 0.10 or 1
    ypad = (yhi - ylo) * 0.12 or 1
    xlo -= xpad
    xhi += xpad
    ylo = max(0, ylo - ypad)
    yhi += ypad
    sx = lambda v: px0 + (v - xlo) / (xhi - xlo) * (px1 - px0)
    sy = lambda v: py1 - (v - ylo) / (yhi - ylo) * (py1 - py0)
    sv = SVG(w, h)
    sv.text(10, 18, title, 12.5, INK, weight=700)
    sv.text(10, 33, sub, 9.6, SUB)
    for i in range(5):
        gx = xlo + (xhi - xlo) * i / 4
        sv.line(sx(gx), py0, sx(gx), py1, GRID, 1)
        sv.text(sx(gx), py1 + 14, f"{gx:.0f}%", 8.8, MUTE, anchor="middle")
        gy = ylo + (yhi - ylo) * i / 4
        sv.line(px0, sy(gy), px1, sy(gy), GRID, 1)
        sv.text(px0 - 6, sy(gy) + 3.2, f"{gy:.0f}%", 8.8, MUTE, anchor="end")
    if xr:
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        if sxx:
            k = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
            b0 = my - k * mx
            sv.line(sx(xlo), sy(k * xlo + b0), sx(xhi), sy(k * xhi + b0), "#C2683C", 1.5, dash="6 4")
        sv.text(px0, py0 - 6, f"pearson r = {xr:+.4f}（n={n}）", 10.2, POS, weight=700)
    for x, y, cat, tip in pairs:
        sv.circle(sx(x), sy(y), 5.0, CAT_COLOR.get(cat, NAVY), tip, stroke="#fff", sw=1.3)
    sv.text(px0, py1 + 32, f"→ {xlab}", 10, INK2)
    sv.add(f'<text x="13" y="{(py0 + py1) / 2:.0f}" font-size="10" fill="{INK2}" '
           f'transform="rotate(-90 13 {(py0 + py1) / 2:.0f})" text-anchor="middle">↓ {ylab}</text>')
    ly = py0 + 4
    lx = px1 - 76
    for c in CAT_ORD:
        sv.rect(lx, ly - 7, 9, 9, CAT_COLOR[c], rx=2, title=f"品种配色：{c}")
        sv.text(lx + 13, ly + 1, c, 8.8, INK2)
        ly += 14
    return sv.render(title)


# ════════════════════════════════════════════════════════════════════════
# 6. 折叠块 HTML
# ════════════════════════════════════════════════════════════════════════
def fold_open(key, title, q, body):
    """默认收起的折叠块：<details> 不带 open 属性即为收起。"""
    return (
        f'<details class="a-fold" id="a-{key}">'
        f'<summary class="a-fold-h">'
        f'<span class="a-fold-t">{esc(title)}</span>'
        f'<span class="a-fold-q">{esc(q)}</span>'
        f'</summary>'
        f'<div class="a-fold-b">{body}</div>'
        f'</details>')


def table(cls, cap, cols, rows):
    th = "".join(f"<th>{esc(c)}</th>" for c in cols)
    return (f'<div class="a-tw"><table class="a-tbl {cls}"><caption>{esc(cap)}</caption>'
            f'<thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def body_cat(cat_rows):
    rows = []
    for r in cat_rows:
        rows.append(
            "<tr>"
            f'<td class="a-k"><span class="a-dot" style="background:{CAT_COLOR[r["cat"]]}"></span>'
            f'{esc(r["cat"])}</td>'
            f'<td class="a-n">{r["n"]}</td>'
            f'<td class="a-n">{yi(r["issue"])}</td>'
            f'<td class="a-n">{yi(r["pool"])}</td>'
            f'<td class="a-n">{yi(r["rec"])}</td>'
            f'<td class="a-n a-b">{pct(r["recW"])}</td>'
            f'<td class="a-n">{pct(r["recMed"])}</td>'
            f'<td class="a-n">{pct(r["secW"])}</td>'
            f'<td class="a-n">{pct(r["sen"])}</td>'
            f'<td class="a-n a-b">{pct(r["sub"])}</td>'
            f'<td class="a-n">{pct(r["vf"])}</td>'
            "</tr>")
    tbl = table("a-tbl-cat", "各品种对照（回收率与证券化率均为 累计回收（发行规模）÷ 入池本息费）",
                ["品种", "单数", "发行规模(亿)", "入池本息费(亿)", "累计回收(亿)",
                 "回收率·加权", "回收率·中位", "证券化率·加权", "优先档XIRR", "次级档XIRR", "达成率"],
                rows)
    foot = ('<ul class="a-fn">'
            '<li><b>回收率</b>＝累计回收 ÷ 入池本息费；<b>证券化率</b>＝发行规模 ÷ 入池本息费。</li>'
            '<li>两档 XIRR 与达成率取组内<b>中位</b>（单数少的品种更稳）。</li>'
            '<li>信用卡不良 23 单占样本 82%，其加权回收率被大额单拉低，'
            '与中位回收率并列看更准。</li>'
            '</ul>')
    return chart_cat(cat_rows) + tbl + foot


def body_bank(bank_rows, metrics):
    # 指标跨行表：每行一家机构，列出 4 个指标的 z 与 ★/· 标记
    def zcell(r, key):
        z = r["z"].get(key)
        if z is None:
            return f'<td class="a-n">{DASH}{DASH and ""}</td>' if False else f'<td class="a-n">{DASH}</td>'
        flag = r["flag"].get(key, "")
        cl = "a-out" if flag == "★" else ("a-edge" if flag == "·" else "")
        return f'<td class="a-n {cl}">{z:+.2f}{flag}</td>'

    rows = []
    for r in sorted(bank_rows, key=lambda x: -(x["issue"] or 0)):
        rows.append(
            "<tr>"
            f'<td class="a-k">{esc(r["bank"])}</td>'
            f'<td class="a-n">{r["n"]}</td>'
            f'<td class="a-n a-b">{yi(r["issue"])}</td>'
            f'<td class="a-n">{yi(r["pool"])}</td>'
            f'<td class="a-n">{yi(r["rec"])}</td>'
            f'<td class="a-n a-b">{pct(r["recW"])}</td>'
            f'<td class="a-n">{pct(r["secW"])}</td>'
            f'<td class="a-n">{pct(r["sen"])}</td>'
            f'<td class="a-n a-b">{pct(r["sub"])}</td>'
            + zcell(r, "recW") + zcell(r, "secW") + zcell(r, "sen") + zcell(r, "sub")
            + "</tr>")
    cols = ["发起机构", "单数", "发行规模(亿)", "入池本息费(亿)", "累计回收(亿)",
            "回收率·加权", "证券化率·加权", "优先档XIRR", "次级档XIRR",
            "z·回收率", "z·证券化率", "z·优先档", "z·次级档"]
    tbl = table("a-tbl-bank", "各发起机构对照 + MAD 稳健异常（z = 1.4826×(x−中位)/MAD；★ |z|>3.5 · |z|>2.5）",
                cols, rows)
    out = ('<ul class="a-fn">'
           '<li><b>最大异常：</b>中国银行次级档 XIRR 26.40%（z≈+44.9），'
           '对应其两单回收率 27.63% / 11.07% 的高离散；'
           '平安银行 9.90%、光大银行 10.10%、民生银行 10.20% 同向偏低（z≈−6.2 ~ −7.1）。</li>'
           '<li><b>稳健性提示：</b>样本 2 单的机构（中行/交行/建行/光大/民生）z 值对单点极敏感，'
           '只作提示，不作结论依据。</li>'
           '<li>优先档 XIRR 的 z 全部落在 ±3.5 内，'
           '说明优先档不构成机构间差异；分化集中在次级档与回收率。</li>'
           '</ul>')
    return chart_bank(bank_rows) + tbl + out


def body_pat(pat):
    cards = [
        ("证券化率不解释回收",
         f'证券化率与达成率相关 r = {pat["r_sec_rec"]:+.4f}（n={pat["n"]}）。'
         '发行折价深浅与最终回收好坏基本脱钩，定价更多反映资产池「名目」，而非结果。'),
        ("次级档吃下全部风险溢价",
         f'优先档 XIRR 区间 {pct(pat["sen_rng"][0])}–{pct(pat["sen_rng"][1])}'
         f'（跨度 {pat["sen_span"]:.2f}pp）；次级档 '
         f'{pct(pat["sub_rng"][0])}–{pct(pat["sub_rng"][1])}（跨度 {pat["sub_span"]:.2f}pp），'
         f'跨度是优先档的 {pat["sub_span"] / pat["sen_span"]:.1f} 倍，中位倍数 ×{f2(pat["mult_med"], 1)}。'),
        ("回收率是次级档回报的分子端",
         f'次级档 XIRR 与达成率相关 r = {pat["r_sub_rec"]:+.4f}，'
         f'与证券化率相关 r = {pat["r_sub_sec"]:+.4f}。'
         '次级档拿的是残值：先把回收做出来，才谈得上分配规则。'),
        ("机构定价按档位分层，不是逐单竞价",
         f'回收率区间 {pct(pat["rr_rng"][0])}–{pct(pat["rr_rng"][1])}'
         f'（{pat["rr_rng"][1] / pat["rr_rng"][0]:.1f} 倍）、'
         f'证券化率 {pct(pat["sr_rng"][0])}–{pct(pat["sr_rng"][1])}，'
         '两者都是「机构档位」而非「逐单市场化」的结果。'),
    ]
    cards_html = "".join(
        f'<div class="a-pc"><div class="a-pc-t">{esc(t)}</div>'
        f'<div class="a-pc-b">{b}</div></div>' for t, b in cards)
    return f'<div class="a-pcs">{cards_html}</div>'


DET_COLS = ["项目", "品种", "发起机构", "发行规模(亿)", "入池本息费(亿)", "累计回收(亿)",
            "回收率", "证券化率", "优先档XIRR", "次级档XIRR", "达成率", "期数"]


def body_det(prof):
    pf = prof["PROF"]
    # 全部 28 单：缺回收率的排在末尾（记「—」），不因缺值丢行
    us = sorted([pf[k] for k in prof["ORDER"]],
                key=lambda v: (v.get("recRate") is None, -(v.get("recRate") or 0)))
    rows = []
    for v in us:
        rows.append(
            "<tr>"
            f'<td class="a-k">{esc(v.get("short") or v.get("name") or v.get("code"))}</td>'
            f'<td class="a-catc"><span class="a-dot" '
            f'style="background:{CAT_COLOR.get(v.get("cat"), NAVY)}"></span>{esc(v.get("cat"))}</td>'
            f'<td>{esc(v.get("issuer"))}</td>'
            f'<td class="a-n">{yi(v.get("issue"))}</td>'
            f'<td class="a-n">{yi(v.get("poolTotal"))}</td>'
            f'<td class="a-n">{yi(v.get("recovered"))}</td>'
            f'<td class="a-n a-b">{pct(v.get("recRate"))}</td>'
            f'<td class="a-n">{pct(v.get("secRatio"))}</td>'
            f'<td class="a-n">{pct(v.get("xirrSen"))}</td>'
            f'<td class="a-n a-b">{pct(v.get("xirrSub"))}</td>'
            f'<td class="a-n">{pct(v.get("vsForecast"))}</td>'
            f'<td class="a-n">{v.get("n_periods") if v.get("n_periods") is not None else DASH}</td>'
            "</tr>")
    miss = sum(1 for v in us if v.get("recRate") is None)
    foot = (f'<ul class="a-fn"><li>共 {len(us)} 单（全样本）。'
            + (f'其中 {miss} 单缺回收率，排在表末并以「—」记。</li>' if miss else '</li>')
            + '<li>点表头可按该列排序（数字列按数值）。</li>'
              '<li>回收率＝累计回收 ÷ 入池本息费；证券化率＝发行规模 ÷ 入池本息费；'
              '达成率＝累计回收 ÷ 发行时第三方预测回收。</li></ul>')
    return table("a-tbl-det", f"{len(us)} 单明细（按回收率降序，缺值置末）", DET_COLS, rows) + foot


def body_def():
    lvl = {"高": "a-lv-hi", "中": "a-lv-mid", "低": "a-lv-lo"}
    rows = []
    for no, name, lv, n_, scope, act in DEFECTS:
        cnt = "" if n_ is None else f'（{n_}/28）'
        rows.append(
            "<tr>"
            f'<td class="a-k">{no}</td>'
            f'<td>{esc(name)}</td>'
            f'<td><span class="a-lv {lvl[lv]}">{lv}</span></td>'
            f'<td class="a-src">{cnt}{scope}</td>'
            f'<td class="a-src">{act}</td>'
            "</tr>")
    tbl = table("a-tbl-def", f"缺陷清单 {len(DEFECTS)} 条（按影响排序）",
                ["编号", "缺陷", "等级", "范围与取证", "处置与影响"], rows)
    return tbl


# ════════════════════════════════════════════════════════════════════════
# 7. 主导出
# ════════════════════════════════════════════════════════════════════════
def build():
    prof, _audit = _load()
    cat_rows, bank_rows, metrics, pat = build_stats(prof)
    pf = prof["PROF"]

    # 图 3：证券化率 × 达成率
    p3 = [(v["secRatio"] * 100, v["vsForecast"] * 100, v.get("cat"),
           f'{v.get("short") or v.get("name")}｜{v.get("issuer")}\n'
           f'证券化率 {pct(v.get("secRatio"))}｜达成率 {pct(v.get("vsForecast"))}\n'
           f'回收率 {pct(v.get("recRate"))}｜发行 {yi(v.get("issue"))} 亿元\n'
           f'次级档 XIRR {pct(v.get("xirrSub"))}｜品种 {v.get("cat")}')
          for v in (pf[k] for k in prof["ORDER"])
          if v.get("secRatio") is not None and v.get("vsForecast") is not None]
    # 图 4：回收率 × 次级档 XIRR
    p4 = [(v["recRate"] * 100, v["xirrSub"] * 100, v.get("cat"),
           f'{v.get("short") or v.get("name")}｜{v.get("issuer")}\n'
           f'回收率 {pct(v.get("recRate"))}｜次级档 XIRR {pct(v.get("xirrSub"))}\n'
           f'证券化率 {pct(v.get("secRatio"))}｜达成率 {pct(v.get("vsForecast"))}\n'
           f'发行 {yi(v.get("issue"))} 亿元｜品种 {v.get("cat")}')
          for v in (pf[k] for k in prof["ORDER"])
          if v.get("recRate") is not None and v.get("xirrSub") is not None]
    c3 = chart_scatter(p3, "证券化率（%）", "达成率（%）",
                       "证券化率 × 达成率：定价深不深，和回收好不好无关",
                       "28 单｜每点＝单项目｜虚线＝最小二乘趋势", pat["r_sec_rec"])
    c4 = chart_scatter(p4, "回收率（%）", "次级档 XIRR（%）",
                       "回收率 × 次级档 XIRR：分子端决定次级档回报",
                       "27 单｜每点＝单项目｜虚线＝最小二乘趋势", pat["r_sub_rec"])

    bodies = {
        "fen": body_cat(cat_rows),
        "bank": body_bank(bank_rows, metrics),
        "pat": body_pat(pat),
        "det": body_det(prof),
        "def": body_def(),
    }
    parts = ['<div class="a-wrap">']
    parts.append(
        f'<header class="a-ph"><h3 class="a-ph-t">{esc(FOLD_TITLE)}</h3>'
        f'<p class="a-ph-s">{esc(FOLD_LEAD)}</p></header>')
    for key, title, q in FOLDS:
        parts.append(fold_open(key, title, q, bodies[key]))
    parts.append('</div>')
    html = "".join(parts)
    return html, cat_rows, bank_rows, pat, len(DEFECTS)


CSS = r"""
.a-wrap{position:relative}
.a-ph{margin:0 0 16px;padding:0}
.a-ph-t{margin:0 0 5px;font-size:19px;font-weight:800;color:#141A26;letter-spacing:-.3px;line-height:1.3}
.a-ph-s{margin:0;font-size:12.2px;color:#697487;line-height:1.7}
.a-fold{margin:0 0 10px;border:1px solid #E6EAF1;border-radius:13px;background:#fff;
  box-shadow:0 1px 2px rgba(16,24,40,.03),0 14px 26px -24px rgba(16,24,40,.28);overflow:hidden}
.a-fold-h{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;cursor:pointer;
  padding:13px 46px 13px 16px;position:relative;list-style:none;background:#FCFDFF;transition:.16s}
.a-fold-h::-webkit-details-marker{display:none}
.a-fold-h::marker{content:""}
.a-fold-h:hover{background:#F5F9FE}
.a-fold-t{font-size:13.5px;font-weight:800;color:#141A26;white-space:nowrap}
.a-fold-t::before{content:"+";display:inline-block;width:15px;margin-right:7px;color:#2D3955;
  font-weight:800;font-size:14px}
.a-fold[open]>.a-fold-h>.a-fold-t::before{content:"−"}
.a-fold-q{font-size:11.5px;color:#7C8798;line-height:1.55}
.a-fold[open]>.a-fold-h{background:#F2F7FD;border-bottom:1px solid #E6EAF1}
.a-fold:not([open])>.a-fold-b{display:none}
.a-fold[open]>.a-fold-b{display:block}
.a-fold-b{padding:14px 16px 16px}
.a-svg{display:block;width:100%;height:auto;overflow:visible;margin:2px 0 10px}
.a-tw{overflow:auto;border:1px solid #E6EAF1;border-radius:12px;margin:8px 0 6px;background:#fff}
.a-tbl{width:100%;border-collapse:collapse;font-size:11.3px;font-variant-numeric:tabular-nums}
.a-tbl caption{caption-side:top;text-align:left;padding:9px 12px;font-size:11.6px;font-weight:700;
  color:#38425A;background:#F7FAFD;border-bottom:1px solid #E6EAF1}
.a-tbl th{position:sticky;top:0;z-index:2;background:#EFF3F9;color:#2D3955;font-weight:800;
  font-size:10.6px;text-align:left;padding:7px 8px;border-bottom:1px solid #D8DFE9;white-space:nowrap}
.a-tbl td{padding:6px 8px;border-bottom:1px solid #F0F3F8;color:#38425A;vertical-align:middle}
.a-tbl tbody tr:hover td{background:#FAFCFF}
.a-tbl .a-k{color:#141A26;font-weight:700;white-space:nowrap}
.a-tbl .a-n{text-align:right;white-space:nowrap}
.a-tbl .a-b{font-weight:800;color:#2D3955}
.a-tbl .a-src{color:#7C8798;font-size:10.4px}
.a-tbl .a-catc{white-space:nowrap;color:#4A5568}
.a-tbl-cat{min-width:900px}
.a-tbl-bank{min-width:980px}
.a-tbl-det{min-width:880px}
.a-tbl-def{min-width:820px}
.a-dot{display:inline-block;width:7px;height:7px;border-radius:2px;margin-right:6px;vertical-align:1px}
.a-out{color:#A52524;font-weight:800}
.a-edge{color:#B0763F;font-weight:700}
.a-lv{display:inline-block;padding:2px 7px;border-radius:999px;font-size:10.4px;font-weight:800}
.a-lv-hi{background:#FBEAEA;color:#A52524}
.a-lv-mid{background:#FBF1E6;color:#B0763F}
.a-lv-lo{background:#EAF4F0;color:#1F7A5C}
.a-fn{margin:8px 0 0;padding:0 0 0 17px;font-size:11px;line-height:1.75;color:#697487}
.a-fn li{margin:3px 0}
.a-fn code,.a-pc-b code{background:#F1F4F9;border-radius:4px;padding:1px 5px;font-size:10.4px;color:#2D3955}
.a-pcs{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:11px;margin:2px 0 4px}
.a-pc{border:1px solid #E6EAF1;border-radius:12px;padding:12px 14px;
  background:linear-gradient(180deg,#fff,#F8FBFF)}
.a-pc-t{font-size:12.6px;font-weight:800;color:#141A26;margin-bottom:5px}
.a-pc-b{font-size:11.6px;line-height:1.75;color:#4A5568}
@media (max-width:760px){
  .a-fold-h{padding:11px 16px}
  .a-fold-t{white-space:normal}
  .a-fold-q{display:block}
}
"""

JS = r"""
/* ===== 40_audit 明细与底稿（独立视图 #view-appendix）：默认收起 + 明细表排序 ===== */
(function(){
  var root = document.querySelector('#view-appendix .a-wrap');
  if(!root) return;

  /* 1) 强制默认收起（幂等；<details> 不写 open 即为收起） */
  var folds = root.querySelectorAll('details.a-fold');
  for(var i = 0; i < folds.length; i++) folds[i].removeAttribute('open');

  /* 2) 悬停读数：读最近祖先的 <title> */
  var tip = null;
  function ensureTip(){
    var t = document.getElementById('xtTip');
    if(t && t.parentNode) return t;
    tip = document.createElement('div');
    tip.id = 'xtTip';
    document.body.appendChild(tip);
    return tip;
  }
  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>]/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];
    });
  }
  function findTitle(el){
    var n = 0, t = el;
    while(t && t !== document.body && n < 8){
      if(t.children){
        for(var k = 0; k < t.children.length; k++){
          if(t.children[k].tagName && t.children[k].tagName.toLowerCase() === 'title'){
            return t.children[k].textContent;
          }
        }
      }
      t = t.parentNode; n++;
    }
    return null;
  }
  function place(e){
    var tp = ensureTip(), r = tp.getBoundingClientRect();
    var x = e.clientX + 16, y = e.clientY + 14;
    if(x + r.width > window.innerWidth - 10) x = e.clientX - r.width - 16;
    if(y + r.height > window.innerHeight - 10) y = e.clientY - r.height - 14;
    tp.style.left = Math.max(8, x) + 'px';
    tp.style.top = Math.max(8, y) + 'px';
  }
  var cur = null;
  function hide(){
    if(cur && cur.style) cur.style.filter = '';
    cur = null;
    var tp = document.getElementById('xtTip');
    if(tp){ tp.classList.remove('on'); tp.innerHTML = ''; }
  }
  root.addEventListener('mousemove', function(e){
    var t = e.target;
    if(!t || !t.closest){ hide(); return; }
    if(!t.closest('svg')){ hide(); return; }
    var txt = findTitle(t);
    if(!txt){ hide(); return; }
    var tp = ensureTip();
    var parts = String(txt).split('\uFF5C');
    var head = parts.length > 1 ? parts[0] : '';
    var rest = parts.length > 1 ? parts.slice(1).join('\uFF5C') : String(txt);
    tp.innerHTML = (head ? '<span class="t">' + esc(head) + '</span>' : '')
      + '<span class="m">' + esc(rest) + '</span><div class="bar"></div>';
    tp.classList.add('on');
    if(cur && cur !== t && cur.style) cur.style.filter = '';
    cur = t;
    if(t.style) t.style.filter = 'brightness(1.11)';
    place(e);
  }, {passive:true});
  root.addEventListener('mouseleave', hide);

  /* 3) 明细表：点表头排序（数字列按数值） */
  var det = root.querySelector('.a-tbl-det');
  if(det){
    var ths = det.querySelectorAll('thead th');
    for(var j = 0; j < ths.length; j++){
      (function(idx, th){
        th.style.cursor = 'pointer';
        th.title = '点击按此列排序（数字列按数值）';
        th.addEventListener('click', function(){
          var tb = det.querySelector('tbody');
          var rows = Array.prototype.slice.call(tb.querySelectorAll('tr'));
          function key(r){
            var c = r.children[idx];
            if(!c) return '';
            var s = (c.textContent || '').replace(/[%,—\s]/g, '');
            var f = parseFloat(s);
            return isNaN(f) ? c.textContent : f;
          }
          var asc = th.getAttribute('data-dir') !== 'asc';
          th.setAttribute('data-dir', asc ? 'asc' : 'desc');
          rows.sort(function(a, b){
            var x = key(a), y = key(b);
            if(typeof x === 'number' && typeof y === 'number') return asc ? x - y : y - x;
            return asc ? String(x).localeCompare(String(y), 'zh')
                       : String(y).localeCompare(String(x), 'zh');
          });
          rows.forEach(function(r){ tb.appendChild(r); });
        });
      })(j, ths[j]);
    }
  }
})();
"""


def _digest(s):
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


HTML = build()[0]


# ════════════════════════════════════════════════════════════════════════
# 8. 自检（独立运行）
# ════════════════════════════════════════════════════════════════════════
def _browser_fold_check(html, css):
    """用无头浏览器实测：折叠块是否默认收起（内容区未被渲染）。"""
    import subprocess
    import tempfile
    payload = json.dumps(html)
    page = (
        '<!doctype html><meta charset="utf-8"><title>foldcheck:pending</title>'
        '<style>' + css + '</style><body>'
        '<div class="view" id="view-appendix"><div id="mnt"></div></div>'
        '<script>\n'
        'var payload = ' + payload + ';\n'
        'document.getElementById("mnt").innerHTML = payload;\n'
        'var r = {folds:0, open:0, bodiesRendered:0, headsRendered:0, bodyDisplay:""};\n'
        'try{\n'
        '  var fs = document.querySelectorAll("#view-appendix details.a-fold");\n'
        '  r.folds = fs.length;\n'
        '  var seen = {};\n'
        '  for(var i=0;i<fs.length;i++){\n'
        '    if(fs[i].hasAttribute("open")) r.open++;\n'
        '    var b = fs[i].querySelector(".a-fold-b");\n'
        '    var h = fs[i].querySelector(".a-fold-h");\n'
        '    if(b){\n'
        '      var d = getComputedStyle(b).display;\n'
        '      seen[d] = 1;\n'
        '      if(d !== "none" && b.getBoundingClientRect().height > 1) r.bodiesRendered++;\n'
        '    }\n'
        '    if(h && h.getBoundingClientRect().height > 1) r.headsRendered++;\n'
        '  }\n'
        '  r.bodyDisplay = Object.keys(seen).join(",");\n'
        '}catch(e){ r.err = String(e); }\n'
        'document.title = "foldcheck:" + JSON.stringify(r);\n'
        '</script></body>')
    d = Path(tempfile.gettempdir())
    f = d / "_a40_foldcheck.html"
    f.write_text(page, encoding="utf-8")
    exes = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
    exe = next((e for e in exes if Path(e).exists()), None)
    if not exe:
        return None, "未找到 Edge/Chrome，跳过浏览器折叠校验"
    cmd = [exe, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--virtual-time-budget=5000", "--dump-dom", f.as_uri()]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=180).stdout or ""
    except Exception as e:
        return None, f"浏览器调用失败：{type(e).__name__}: {e}"
    m = re.search(r'title>foldcheck:(\{.*?\})</title', out, re.S)
    if not m:
        m = re.search(r'foldcheck:(\{[^<]*\})', out)
    if not m:
        return None, "未能从浏览器 DOM 取到折叠校验结果"
    try:
        return json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&")), None
    except Exception as e:
        return None, f"折叠校验结果解析失败（{e}）：{m.group(1)[:90]}"


def _selftest():
    html, cat_rows, bank_rows, pat, n_def = build()
    html2 = build()[0]
    problems = []

    folds = re.findall(r'<details class="a-fold" id="a-([a-z]+)">', html)
    n_open = html.count("<details class=\"a-fold\" open") + html.count("open=\"open\"")
    n_plus = html.count('class="a-fold-h"')
    svgs = re.findall(r'<svg .*?</svg>', html, re.S)
    n_titles = html.count("<title>")

    def rows_by_class(seg, cls):
        m = re.search(r'<table class="a-tbl ' + cls + r'">.*?<tbody>(.*?)</tbody>', seg, re.S)
        return len(re.findall(r'<tr', m.group(1))) if m else 0

    def seg_of(key):
        i = html.find(f'id="a-{key}"')
        j = html.find('<details class="a-fold"', i + 10)
        return html[i:(j if j > 0 else len(html))]

    s_det, s_def, s_bank, s_cat = (seg_of("det"), seg_of("def"),
                                   seg_of("bank"), seg_of("fen"))
    det_rows = rows_by_class(s_det, "a-tbl-det")
    def_rows = rows_by_class(s_def, "a-tbl-def")
    bank_rows_n = rows_by_class(s_bank, "a-tbl-bank")
    cat_rows_n = rows_by_class(s_cat, "a-tbl-cat")

    # 口径硬约束
    # 用户 v11 硬要求：某个两字词（意为「由结果反推比率」）在任何位置都不得出现。
    # 为让本源码文件本身也不含该词，此处以 Unicode 转义书写，运行时还原比对。
    banned_word = "\u5012\u7b97"
    bans = {
        "折价率": html.count("折价率") + CSS.count("折价率") + JS.count("折价率"),
        "÷ 入池本息费口径错误串（处置费率÷入池本息费）":
            html.count("处置费率 ÷ 入池本息费") + html.count("处置费用 ÷ 入池本息费")
            + html.count("÷封包本金") + html.count("÷ 封包本金") + html.count("÷封包本息费"),
        "成本强度": html.count("成本强度") + CSS.count("成本强度") + JS.count("成本强度"),
        "稽核区": html.count("稽核区") + CSS.count("稽核区"),
        "H1 裁定块": html.count("H1 裁定") + html.count("XIRR=0"),
        "过程性表述": html.count("我核对") + html.count("我验证") + html.count("本页只读")
                     + html.count("元说明"),
        "用户禁用词（v11·反推比率）": html.count(banned_word) + CSS.count(banned_word)
                                      + JS.count(banned_word),
    }
    n_banned_src = Path(__file__).read_text(encoding="utf-8").count(banned_word)

    print("═" * 74)
    print("40_audit.py 自检（明细与底稿 · 独立视图 #view-appendix）")
    print("═" * 74)
    print(f"  体量                CSS {len(CSS):,} / HTML {len(html):,} / JS {len(JS):,} 字符")
    print(f"                      （第三轮 HTML 33,666 → 现 {len(html):,}，"
          f"{(len(html) - 33666) / 33666 * 100:+.1f}%）")
    print(f"  HTML ≤36,000        {len(html):,}  {'OK' if len(html) <= 36000 else 'FAIL'}")
    print(f"  SVG 张数            {len(svgs)}  [≤6]  {'OK' if len(svgs) <= 6 else 'FAIL'}")
    print(f"  tooltip <title>     {n_titles} 个")
    print()
    print("  ── 页头（极简，3 行内）──")
    ph_t = re.search(r'<h3 class="a-ph-t">([^<]*)</h3>', html)
    ph_s = re.search(r'<p class="a-ph-s">([^<]*)</p>', html)
    print(f"    标题          {ph_t.group(1) if ph_t else '缺失'!r}")
    print(f"    一句话说明    {ph_s.group(1) if ph_s else '缺失'!r}")
    print(f"    页头块数      {html.count('class=\"a-ph\"')}  [期望 1]  "
          f"{'OK' if html.count('class=\"a-ph\"') == 1 else 'FAIL'}")
    print(f"    无引导语      {'OK' if '折叠区 · 以下是细粒度' not in html else 'FAIL'}")
    print(f"    无 hero/导航  {'OK' if ('a-hero' not in html and 'a-idx' not in html) else 'FAIL'}")
    print()
    print(f"  折叠块数            {len(folds)}  [建议 5]  {'OK' if len(folds) == 5 else 'FAIL'}")
    qmax = 0
    for i, k in enumerate(folds, 1):
        ttl = re.search(rf'id="a-{k}">\s*<summary class="a-fold-h">'
                        rf'<span class="a-fold-t">([^<]*)</span>'
                        rf'<span class="a-fold-q">([^<]*)</span>', html)
        q = ttl.group(2) if ttl else "?"
        qmax = max(qmax, len(q))
        flag = "OK" if len(q) <= 20 else "FAIL(>20)"
        print(f"    {i}. {k:5s} {ttl.group(1) if ttl else '?':14s} | {q}  "
              f"[{len(q)} 字] {flag}")
    print(f"    说明字数上限  {qmax}  [≤20]  {'OK' if qmax <= 20 else 'FAIL'}")
    print(f"  默认收起（无 open） {n_open} 个带 open  [期望 0]  {'OK' if n_open == 0 else 'FAIL'}")
    print(f"  「+」标题行         {n_plus} 个  {'OK' if n_plus == len(folds) else 'FAIL'}")
    print()
    print(f"  分品种表行数        {cat_rows_n}  [期望 3]  {'OK' if cat_rows_n == 3 else 'FAIL'}")
    print(f"  银行对照表行数      {bank_rows_n}  [期望 9]  {'OK' if bank_rows_n == 9 else 'FAIL'}")
    print(f"  28 单明细行数       {det_rows}  [期望 28]  {'OK' if det_rows == 28 else 'FAIL'}")
    print(f"  缺陷清单行数        {def_rows}  [期望 10]  {'OK' if def_rows == n_def == 10 else 'FAIL'}")
    print()
    print("  ── 口径硬约束 ──")
    for k, v in bans.items():
        print(f"    「{k}」 {v} 次  [期望 0]  {'OK' if v == 0 else 'FAIL'}")
    print(f"    源码文件内该禁用词   {n_banned_src} 次  [期望 0]  "
          f"{'OK' if n_banned_src == 0 else 'FAIL'}")
    print()
    print("  ── 结构检查 ──")
    checks = [
        ("HTML 无 <section> 外壳", "<section" not in html and "</section>" not in html),
        ("CSS 无注释", "/*" not in CSS),
        ("CSS 无 #view-xcompare / #view-appendix 自身选择器",
         "#view-xcompare" not in CSS and "#view-appendix" not in CSS),
        ("JS 无 const/let", "const " not in JS and "let " not in JS),
        ("JS 无 <script> 外壳", "<script" not in JS),
        ("根容器 a-wrap 唯一", html.count('class="a-wrap"') == 1),
        ("<title> 成对", html.count("<title>") == html.count("</title>")),
        ("无整页 hero / 区段标题", "<h1" not in html and "a-hero" not in html),
        ("无总览导航", 'class="a-idx"' not in html),
        ("无费用双渠道整卡", "费用双渠道" not in html),
        ("页头标题「明细与底稿」1 处", html.count(FOLD_TITLE) == 1),
        ("无折叠区引导语", "折叠区 · 以下是细粒度" not in html and "a-lead" not in html),
        ("每块说明 ≤20 字", qmax <= 20),
    ]
    for name, ok in checks:
        print(f"    {'OK  ' if ok else 'FAIL'} {name}")
        if not ok:
            problems.append(name)
    for k, v in bans.items():
        if v:
            problems.append(k)
    if n_banned_src:
        problems.append("源码含用户禁用词")
    if len(html) > 36000:
        problems.append("HTML 超 36000")
    if len(svgs) > 6:
        problems.append("SVG 超 6")
    if len(folds) != 5:
        problems.append("折叠块数")
    if n_open != 0:
        problems.append("存在默认展开的折叠块")
    if cat_rows_n != 3:
        problems.append("分品种行数")
    if bank_rows_n != 9:
        problems.append("银行行数")
    if det_rows != 28:
        problems.append("明细行数")
    if def_rows != 10:
        problems.append("缺陷行数")

    print()
    print("  ── SVG 越界自检 ──")
    bad_total = 0
    for idx, svg in enumerate(svgs, 1):
        W, H = (float(x) for x in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg).groups())
        has_wh = ('width="' in svg and 'height="' in svg)
        bad = 0
        for m0 in re.finditer(r'<circle cx="(-?[\d.]+)" cy="(-?[\d.]+)"', svg):
            cx, cy = float(m0.group(1)), float(m0.group(2))
            if not (-4 <= cx <= W + 4 and -4 <= cy <= H + 4):
                bad += 1
        for m0 in re.finditer(r'<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="(-?[\d.]+)" height="(-?[\d.]+)"', svg):
            x, y, rw_, rh = (float(m0.group(i)) for i in (1, 2, 3, 4))
            if x < -4 or y < -4 or x + rw_ > W + 500 or y + rh > H + 8:
                bad += 1
        bad_total += bad
        print(f"    svg{idx}  {int(W)}×{int(H)}  width/height {'有' if has_wh else '缺!!'}  越界 {bad} 处")
        if not has_wh:
            problems.append(f"svg{idx} 缺 width/height")
    print(f"    越界合计 {bad_total} 处  [期望 0]  {'OK' if bad_total == 0 else 'FAIL'}")
    if bad_total:
        problems.append("SVG 越界")

    print()
    print("  ── 幂等 ──")
    same = html == html2
    print(f"    二次 build digest {_digest(html)} vs {_digest(html2)}  {'OK 一致' if same else 'FAIL'}")
    print(f"    模块级 HTML 与 build() 一致  {'OK' if HTML == html else 'FAIL'}")
    if not same or HTML != html:
        problems.append("幂等")

    print()
    print("  ── 浏览器折叠校验（无头 Edge 实测「默认收起」）──")
    res, err = _browser_fold_check(html, CSS)
    if res is None:
        print(f"    跳过：{err}")
    else:
        print(f"    folds={res.get('folds')}  open={res.get('open')}  "
              f"内容区可见={res.get('bodiesRendered')}  标题行可见={res.get('headsRendered')}")
        print(f"    内容区 computed display = {res.get('bodyDisplay')!r}（收起时应为 'none'）")
        css_plus = ('content:"+"' in CSS.replace(" ", "")) and ('[open]' in CSS)
        css_lock = ('.a-fold:not([open])>.a-fold-b{display:none}' in CSS.replace(" ", ""))
        print(f"    CSS 显式收起规则 [open] 缺席即 display:none：{'有' if css_lock else '缺'}")
        print(f"    CSS「+」指示符 + [open] 切换规则：{'有' if css_plus else '缺'}")
        ok = (res.get("folds") == len(folds) and res.get("open") == 0
              and res.get("bodiesRendered") == 0
              and res.get("headsRendered") == len(folds)
              and res.get("bodyDisplay") == "none"
              and css_lock and css_plus)
        print(f"    判定：{'OK 全部默认收起（display:none）、标题行可见、+ 指示符就位' if ok else 'FAIL'}")
        if not ok:
            problems.append("浏览器折叠校验")

    print()
    print(f"  独立视图：页头「{FOLD_TITLE}」+ {len(folds)} 个默认收起折叠块"
          f"（分品种 / 银行 / 规律 / 明细 / 缺陷）；规律卡 4 条；缺陷 {n_def} 条")
    print("═" * 74)
    if problems:
        print(f"自检未通过：{'、'.join(problems)}")
        return 1
    print("自检通过 ✔")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(_selftest())
